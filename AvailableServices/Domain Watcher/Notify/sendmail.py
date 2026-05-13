import json
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"
_TEMPLATES_DIR = Path(__file__).resolve().parent / "mail templates"


# ---------------------------------------------------------------------------
#  Config & low-level send
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # Environment variable overrides for secrets
    smtp = cfg.setdefault("smtp", {})
    smtp["host"] = os.environ.get("DOMAINWATCH_SMTP_HOST") or smtp.get("host", "")
    smtp["port"] = int(os.environ.get("DOMAINWATCH_SMTP_PORT", 0) or smtp.get("port", 587))
    smtp["user"] = os.environ.get("DOMAINWATCH_SMTP_USER") or smtp.get("user", "")
    smtp["password"] = os.environ.get("DOMAINWATCH_SMTP_PASSWORD") or smtp.get("password", "")
    smtp["from_email"] = os.environ.get("DOMAINWATCH_SMTP_FROM") or smtp.get("from_email", "")
    to_env = os.environ.get("DOMAINWATCH_SMTP_TO")
    if to_env:
        smtp["to_email"] = [e.strip() for e in to_env.split(",") if e.strip()]
    return cfg


def send_html_email(to_email: str, subject: str, html_body: str, config: dict = None):
    """Send an HTML email via SMTP."""
    if config is None:
        config = _load_config()

    smtp_cfg = config.get("smtp", {})

    if isinstance(to_email, str):
        recipients = [to_email]
    else:
        recipients = to_email

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_cfg.get("from_email", "")
    msg["To"] = ", ".join(recipients)
    msg.set_content("This message contains an HTML advisory.")
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(smtp_cfg.get("host", "smtp.gmail.com"), smtp_cfg.get("port", 587)) as server:
        server.starttls()
        server.login(smtp_cfg.get("user", ""), smtp_cfg.get("password", ""))
        server.send_message(msg)


# ---------------------------------------------------------------------------
#  Alert dispatch (template selection + rendering)
# ---------------------------------------------------------------------------

_SUBJECT_MAP = {
    "initial_entry": "[DomainWatch] Initial Entry — {domain}",
    "new_detection": "[DomainWatch] Initial Entry — {domain}",
    "records_changed": "[DomainWatch] Records Changed — {domain}",
    "content_changed": "[DomainWatch] Content Changed — {domain}",
    "new_iocs": "[DomainWatch] New IOCs Detected — {domain}",
    "new_subdomains": "[DomainWatch] New Subdomains Found — {domain}",
}

_TEMPLATE_MAP = {
    "initial_entry": "NewDetection.html",
    "new_detection": "NewDetection.html",
    "records_changed": "DomainRecordsUpdated.html",
    "content_changed": "DomainContentUpdated.html",
    "new_iocs": "NewIOCsDetected.html",
    "new_subdomains": "NewSubdomainsDetected.html",
}


def send_alert(change_type: str, template_data: dict):
    """Select the correct email template, render it, and send."""
    config = _load_config()
    smtp_cfg = config.get("smtp", {})

    template_name = _TEMPLATE_MAP.get(change_type)
    if not template_name:
        return

    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=True)
    template = env.get_template(template_name)
    html_body = template.render(
        **template_data,
        sender_name=smtp_cfg.get("sender_name", "Analyst"),
    )

    subject = _SUBJECT_MAP.get(change_type, "[DomainWatch] Alert — {domain}").format(
        domain=template_data.get("domain", ""),
    )

    try:
        send_html_email(
            to_email=smtp_cfg.get("to_email", ""),
            subject=subject,
            html_body=html_body,
            config=config,
        )
    except Exception as e:
        print(f"[DomainWatch] Failed to send {change_type} email for {template_data.get('domain', '')}: {e}")