"""SMTP channel for notifications.

Uses aiosmtplib for non-blocking sends. Config is read from the secrets
vault at orchestrator startup and cached on app.state.smtp_config. If
SMTP creds are absent, sends are skipped with a status="skipped" row
in notification_dispatches — the UI surfaces this clearly so the
operator knows to configure SMTP before relying on alerts.

Why a dataclass + module-level send fn instead of a sender class:
testability. Unit tests inject a fake SMTPConfig + monkey-patch the
aiosmtplib call.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from email.message import EmailMessage

import aiosmtplib

log = logging.getLogger(__name__)


@dataclass
class SMTPConfig:
    host: str
    port: int = 587
    user: str = ""
    password: str = ""
    from_addr: str = ""
    use_tls: bool = True   # SSL on connect (port 465)
    start_tls: bool = True  # STARTTLS upgrade (port 587)

    @property
    def configured(self) -> bool:
        return bool(self.host and self.from_addr)


def _classify_smtp_error(exc: Exception) -> str:
    """Map common aiosmtplib failures into a single-line analyst-friendly
    note. Raw stack traces in the UI just stress people out."""
    name = type(exc).__name__
    msg = str(exc)[:240]
    if "Authentication" in name or "auth" in msg.lower():
        return f"SMTP auth failed: check SMTP_USER / SMTP_PASS. ({msg})"
    if "Connect" in name or "name resolution" in msg.lower():
        return f"SMTP host unreachable: check SMTP_HOST / SMTP_PORT. ({msg})"
    if "Timeout" in name:
        return f"SMTP timeout: server slow or blocked by firewall. ({msg})"
    return f"{name}: {msg}"


async def send_email(
    cfg: SMTPConfig,
    *,
    to_addr: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
) -> tuple[bool, str | None]:
    """Send an email. Returns (success, error_message_or_none).

    Doesn't raise — failures are returned so the dispatcher can persist
    the error onto the dispatch row. Idempotent enough: the caller is
    expected to dedupe events upstream (orchestrator does this via
    `event_ref` lookups).
    """
    if not cfg.configured:
        return False, "SMTP not configured (set SMTP_HOST + SMTP_FROM in secrets vault)"

    msg = EmailMessage()
    msg["From"] = cfg.from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body_text)
    if body_html:
        # Multipart: text fallback + HTML primary.
        msg.add_alternative(body_html, subtype="html")

    try:
        # aiosmtplib picks the right behaviour based on use_tls / start_tls:
        #   port 465 + use_tls=True   -> implicit SSL
        #   port 587 + start_tls=True -> opportunistic STARTTLS
        #   port 25  + both False     -> plain (lab / internal relays only)
        await aiosmtplib.send(
            msg,
            hostname=cfg.host,
            port=cfg.port,
            username=cfg.user or None,
            password=cfg.password or None,
            use_tls=cfg.use_tls and cfg.port == 465,
            start_tls=cfg.start_tls and cfg.port == 587,
            timeout=20,
        )
        log.info("smtp_sent to=%s subject=%r", to_addr, subject[:80])
        return True, None
    except Exception as exc:
        err = _classify_smtp_error(exc)
        log.warning("smtp_send_failed to=%s err=%s", to_addr, err)
        return False, err
