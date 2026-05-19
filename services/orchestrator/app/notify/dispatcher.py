"""Notification dispatcher — match events to rules, render, send, audit.

Flow:
  1. Event source posts to /internal/notify with {event_type, event_ref,
     payload}.
  2. dispatch_event() loads all active rules for that event_type.
  3. For each rule, eval_filter() checks the rule's filter against the
     payload. Filters are simple JSON predicates (see below).
  4. For matching rules, the rule's channel renders + sends.
  5. Every attempt (sent / failed / skipped) lands in
     orchestrator.notification_dispatches.

Filter language (intentionally tiny — extend per event type as needed):
  {}                           -> always matches
  {"severity_min": "high"}     -> payload.severity in [high, critical]
  {"change_types": ["dns"]}    -> payload.change_type in the list
  {"product_match": true}      -> payload has affected_products
                                   intersected with CMDB profile
                                   (event source does the intersection
                                    upstream; we just look for the flag)
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NotificationDispatch, NotificationRule
from app.notify.smtp import SMTPConfig, send_email

log = logging.getLogger(__name__)


# Severity ladder for "severity_min" filter checks. CVEs/threats use these
# labels (NVD's CVSS mapping + analyst overrides).
_SEV_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0, "unknown": 0}


def eval_filter(rule_filter: dict[str, Any], payload: dict[str, Any]) -> bool:
    """Return True if the payload matches the rule filter.

    Empty filter matches everything. Each key narrows; ALL must match
    (AND semantics). Unknown filter keys are ignored (forward-compat).
    """
    if not rule_filter:
        return True

    # severity_min: payload[severity] >= filter[severity_min]
    sev_min = rule_filter.get("severity_min")
    if sev_min:
        ev_sev = (payload.get("severity") or "").lower()
        if _SEV_RANK.get(ev_sev, 0) < _SEV_RANK.get(sev_min.lower(), 0):
            return False

    # change_types: list of allowed change_type values (domainwatch).
    allowed_types = rule_filter.get("change_types")
    if isinstance(allowed_types, list) and allowed_types:
        ev_ct = payload.get("change_type")
        if ev_ct not in allowed_types:
            return False

    # product_match: only fire if the upstream event flagged a product hit.
    # The event source (vuln-intel KEV refresh, threat-intel ingest) sets
    # payload.matches_profile=True when an affected product is in the CMDB.
    if rule_filter.get("product_match"):
        if not payload.get("matches_profile"):
            return False

    return True


def _render_email(event_type: str, payload: dict[str, Any]) -> tuple[str, str, str]:
    """Build (subject, text body, html body) for a generic event payload.

    Per-event-type formatting is kept minimal — analysts get a one-line
    headline + the structured payload below. The aim is "I can act on
    this from my phone" not "this is a marketing newsletter".
    """
    headline = payload.get("title") or payload.get("name") or event_type
    summary = (payload.get("summary") or payload.get("description") or "")[:600]
    ref = payload.get("event_ref") or payload.get("id") or ""
    severity = (payload.get("severity") or "").upper()

    sev_tag = f"[{severity}] " if severity else ""
    subject = f"{sev_tag}{event_type}: {headline}"[:160]

    text_lines = [
        f"Event: {event_type}",
        f"Severity: {severity or 'n/a'}",
        f"Reference: {ref}" if ref else "",
        f"\nHeadline:\n  {headline}\n",
    ]
    if summary:
        text_lines.append(f"Summary:\n  {summary}\n")
    if payload.get("link"):
        text_lines.append(f"View in platform: {payload['link']}")
    text_body = "\n".join(filter(None, text_lines))

    # Minimal styled HTML so Gmail/Outlook render legibly.
    sev_color = {"CRITICAL": "#f85149", "HIGH": "#d29922",
                 "MEDIUM": "#e8a33a", "LOW": "#3fb950"}.get(severity, "#8b949e")
    html_body = f"""<!doctype html><html><body style="font-family:-apple-system,Segoe UI,sans-serif;background:#0d1117;color:#e6edf3;padding:16px;">
<div style="background:#161b22;border:1px solid #21262d;border-radius:8px;padding:18px;max-width:680px;">
<div style="font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:{sev_color};font-weight:700;margin-bottom:6px;">{sev_tag.strip()}{event_type}</div>
<div style="font-size:16px;font-weight:600;line-height:1.4;margin-bottom:14px;">{headline}</div>
{f'<div style="font-size:13px;line-height:1.55;color:#b1bac4;margin-bottom:14px;">{summary}</div>' if summary else ''}
{f'<div style="font-size:11px;color:#8b949e;">Ref: <code style="background:#0d1117;padding:2px 6px;border-radius:4px;">{ref}</code></div>' if ref else ''}
{f'<div style="margin-top:14px;"><a href="{payload.get("link")}" style="color:#2dd4bf;text-decoration:none;">View in platform &rarr;</a></div>' if payload.get('link') else ''}
</div>
<div style="font-size:10px;color:#484f58;margin-top:10px;">TIP Platform · auto-generated alert</div>
</body></html>"""
    return subject, text_body, html_body


async def dispatch_event(
    *,
    session: AsyncSession,
    smtp_config: SMTPConfig | None,
    event_type: str,
    event_ref: str | None,
    payload: dict[str, Any],
) -> dict[str, int]:
    """Fan out an event to every matching active rule.

    Returns a tally {sent, failed, skipped, evaluated} for caller logging.
    Never raises — failures are recorded per-rule.
    """
    rules = (await session.execute(
        select(NotificationRule).where(
            NotificationRule.event_type == event_type,
            NotificationRule.active.is_(True),
        )
    )).scalars().all()

    tally = {"evaluated": len(rules), "sent": 0, "failed": 0, "skipped": 0}

    for rule in rules:
        if not eval_filter(rule.filter or {}, payload):
            tally["skipped"] += 1
            continue

        # Currently smtp only — extending to telegram/webhook is one
        # branch here + a sibling module under app.notify.
        if rule.channel == "smtp":
            if not smtp_config or not smtp_config.configured:
                _audit(session, rule, event_type, event_ref, payload,
                       status="skipped",
                       error="SMTP not configured (set SMTP_* in secrets vault)")
                tally["skipped"] += 1
                continue
            subject, body_text, body_html = _render_email(event_type, payload)
            ok, err = await send_email(
                smtp_config, to_addr=rule.target,
                subject=subject, body_text=body_text, body_html=body_html,
            )
            _audit(session, rule, event_type, event_ref, payload,
                   status="sent" if ok else "failed", error=err)
            tally["sent" if ok else "failed"] += 1
        else:
            _audit(session, rule, event_type, event_ref, payload,
                   status="failed", error=f"channel {rule.channel!r} not implemented")
            tally["failed"] += 1

    await session.commit()
    log.info("dispatch_event type=%s ref=%s tally=%s", event_type, event_ref, tally)
    return tally


def _audit(
    session: AsyncSession,
    rule: NotificationRule | None,
    event_type: str,
    event_ref: str | None,
    payload: dict[str, Any],
    *,
    status: str,
    error: str | None,
) -> None:
    session.add(NotificationDispatch(
        id=uuid.uuid4(),
        rule_id=rule.id if rule else None,
        event_type=event_type,
        event_ref=event_ref,
        channel=rule.channel if rule else "smtp",
        target=rule.target if rule else "",
        status=status,
        error=error,
        payload=payload,
    ))
