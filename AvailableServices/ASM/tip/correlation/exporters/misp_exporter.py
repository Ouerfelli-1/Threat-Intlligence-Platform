"""
MISP Exporter — pushes TIP alerts to a MISP instance as events.
"""
from typing import Optional

from sqlalchemy.orm import Session

from tip.core.integrations.misp_client import MISPClient
from tip.core.logger import get_logger
from tip.core.models import Alert

logger = get_logger(__name__)


class MISPExporter:
    """Export TIP alerts to MISP events."""

    def __init__(self, db: Session, misp_client: Optional[MISPClient] = None):
        self.db = db
        self.misp = misp_client or MISPClient()

    def export_alert(self, alert: Alert) -> Optional[str]:
        """
        Export a single alert as a MISP event.

        Returns the MISP event UUID on success, None on failure.
        """
        if alert.misp_event_id:
            logger.debug("Alert %d already exported to MISP (%s)", alert.id, alert.misp_event_id)
            return alert.misp_event_id

        try:
            # build attributes depending on alert type
            attributes = self._build_attributes(alert)

            event = self.misp.create_event(
                info=alert.title,
                distribution=0,        # org only
                threat_level_id=self._severity_to_threat_level(alert.severity),
                attributes=attributes,
            )
            event_id = event.get("uuid") or event.get("id")

            if event_id:
                alert.misp_event_id = str(event_id)
                self.db.commit()
                logger.info("Exported alert %d → MISP event %s", alert.id, event_id)
                return str(event_id)

        except Exception:
            logger.exception("Failed to export alert %d to MISP", alert.id)

        return None

    # ── private helpers ──────────────────────────────────────────

    def _build_attributes(self, alert: Alert) -> list:
        attrs = []
        raw = alert.raw_data or {}

        if alert.asset and alert.asset.ip_address:
            attrs.append({"type": "ip-dst", "value": alert.asset.ip_address})
        if alert.asset and alert.asset.hostname:
            attrs.append({"type": "domain", "value": alert.asset.hostname})

        # CVE-related
        cves = raw.get("cves") or ([raw["cve_id"]] if raw.get("cve_id") else [])
        for cve_id in cves:
            attrs.append({"type": "vulnerability", "value": cve_id})

        # Leak-related
        if raw.get("leak_source"):
            attrs.append({"type": "text", "value": f"Leak source: {raw['leak_source']}"})

        # IDS / Wazuh
        if raw.get("rule_id"):
            attrs.append({"type": "text", "value": f"Wazuh rule {raw['rule_id']}"})

        # always add a comment
        attrs.append({"type": "comment", "value": alert.description or alert.title})
        return attrs

    @staticmethod
    def _severity_to_threat_level(severity: str) -> int:
        """Map TIP severity → MISP threat_level_id (1-4, 1=high)."""
        return {"CRITICAL": 1, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}.get(
            severity.upper(), 3
        )
