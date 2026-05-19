import logging
import os
from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tip_http import build_resilient_client, fetch_with_resilience
from tip_source_health import SourceHealthRepository

from app.models import KEV

log = logging.getLogger(__name__)


async def _download_json(url: str) -> dict:
    async with build_resilient_client() as client:
        resp = await client.client.get(url)
        resp.raise_for_status()
        return resp.json()


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


async def sync_kev(
    *,
    session: AsyncSession,
    url: str,
    health: SourceHealthRepository,
) -> tuple[int, int, int]:
    result = await fetch_with_resilience("cisa-kev", lambda: _download_json(url), health=health)
    if not result.success or result.value is None:
        return 0, 0, 0

    vulnerabilities = result.value.get("vulnerabilities") or []

    # Pre-load existing cve_ids so we know which incoming rows are NEW
    # — only NEW KEV entries should emit cve.exploited notifications;
    # the rest are just re-confirmations of already-known exploited CVEs.
    existing_ids: set[str] = {
        row[0] for row in (
            await session.execute(select(KEV.cve_id))
        ).all()
    }

    seen = added = 0
    new_kev_emits: list[dict] = []  # notification events to fire post-commit
    for v in vulnerabilities:
        cve_id = v.get("cveID")
        if not cve_id:
            continue
        payload = {
            "cve_id": cve_id,
            "vendor": v.get("vendorProject"),
            "product": v.get("product"),
            "name": v.get("vulnerabilityName"),
            "date_added": _parse_date(v.get("dateAdded")),
            "due_date": _parse_date(v.get("dueDate")),
            "ransomware_use": (v.get("knownRansomwareCampaignUse") or "Unknown").lower() == "known",
            "notes": v.get("notes"),
        }
        seen += 1
        stmt = (
            insert(KEV)
            .values(**payload)
            .on_conflict_do_update(
                index_elements=["cve_id"],
                set_={k: payload[k] for k in payload if k != "cve_id"},
            )
        )
        await session.execute(stmt)
        added += 1
        # Build the emit BEFORE commit so the for-loop has the payload in scope.
        if cve_id not in existing_ids:
            new_kev_emits.append({
                "cve_id": cve_id,
                "vendor": payload["vendor"],
                "product": payload["product"],
                "name": payload["name"],
                "ransomware_use": payload["ransomware_use"],
            })
    await session.commit()

    # Emit notifications for genuinely new KEV entries (post-commit so a
    # failed POST doesn't roll back the KEV refresh itself).
    for ev in new_kev_emits:
        await _notify_exploited(ev)

    return seen, added, 0


async def _notify_exploited(kev: dict) -> None:
    """Fire-and-forget POST to orchestrator /internal/notify.

    Severity = critical when ransomware groups are known to use the CVE
    (CISA's knownRansomwareCampaignUse flag), else high — KEV is already
    a high-confidence "actively exploited" signal.
    """
    orch_url = os.environ.get("ORCHESTRATOR_URL") or "http://orchestrator:8014"
    severity = "critical" if kev.get("ransomware_use") else "high"
    product = " ".join(filter(None, [kev.get("vendor"), kev.get("product")])) or "Unknown product"
    headline = f"{kev['cve_id']} added to CISA KEV: {product}"
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(
                f"{orch_url}/internal/notify",
                json={
                    "event_type": "cve.exploited",
                    "event_ref": kev["cve_id"],
                    "payload": {
                        "title": headline,
                        "summary": kev.get("name") or "",
                        "cve_id": kev["cve_id"],
                        "vendor": kev.get("vendor"),
                        "product": kev.get("product"),
                        "ransomware_use": kev.get("ransomware_use", False),
                        "severity": severity,
                        "link": f"/intelligence/cves/{kev['cve_id']}",
                    },
                },
            )
    except Exception as exc:
        log.warning("kev_notify_failed cve=%s err=%s", kev["cve_id"], exc)
