"""
OpenCTI Exporter — pushes TIP alerts to OpenCTI as STIX reports.
"""
from typing import Optional

from sqlalchemy.orm import Session

from tip.core.integrations.opencti_client import OpenCTIClient
from tip.core.logger import get_logger
from tip.core.models import Alert

logger = get_logger(__name__)


class OpenCTIExporter:
    """Export TIP alerts to OpenCTI reports / indicators."""

    def __init__(self, db: Session, opencti_client: Optional[OpenCTIClient] = None):
        self.db = db
        self.opencti = opencti_client or OpenCTIClient()

    def export_alert(self, alert: Alert) -> Optional[str]:
        """
        Export a single alert to OpenCTI.

        Creates related STIX objects (indicators, vulnerabilities) and
        wraps them in a Report.

        Returns the OpenCTI report ID on success.
        """
        if alert.opencti_report_id:
            logger.debug(
                "Alert %d already exported to OpenCTI (%s)",
                alert.id, alert.opencti_report_id,
            )
            return alert.opencti_report_id

        try:
            object_ids = self._create_stix_objects(alert)

            report = self.opencti.create_report(
                name=alert.title,
                description=alert.description or "",
                object_refs=object_ids,
            )
            report_id = report.get("id")

            if report_id:
                alert.opencti_report_id = report_id
                self.db.commit()
                logger.info("Exported alert %d → OpenCTI report %s", alert.id, report_id)
                return report_id

        except Exception:
            logger.exception("Failed to export alert %d to OpenCTI", alert.id)

        return None

    # ── private helpers ──────────────────────────────────────────

    def _create_stix_objects(self, alert: Alert) -> list:
        """Create the underlying STIX objects and return their IDs."""
        ids = []
        raw = alert.raw_data or {}

        # IP indicator
        if alert.asset and alert.asset.ip_address:
            ip = alert.asset.ip_address
            try:
                ind = self.opencti.create_indicator(
                    name=f"IP: {ip}",
                    pattern=f"[ipv4-addr:value = '{ip}']",
                    pattern_type="stix",
                )
                if ind.get("id"):
                    ids.append(ind["id"])
            except Exception:
                logger.warning("Could not create IP indicator for %s", ip)

        # Domain indicator
        if alert.asset and alert.asset.hostname:
            domain = alert.asset.hostname
            try:
                ind = self.opencti.create_indicator(
                    name=f"Domain: {domain}",
                    pattern=f"[domain-name:value = '{domain}']",
                    pattern_type="stix",
                )
                if ind.get("id"):
                    ids.append(ind["id"])
            except Exception:
                logger.warning("Could not create domain indicator for %s", domain)

        # Vulnerability objects
        cves = raw.get("cves") or ([raw["cve_id"]] if raw.get("cve_id") else [])
        for cve_id in cves:
            try:
                vuln = self.opencti.create_vulnerability(cve_id=cve_id)
                if vuln.get("id"):
                    ids.append(vuln["id"])
            except Exception:
                logger.warning("Could not create vulnerability for %s", cve_id)

        return ids
