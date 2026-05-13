"""
CVE-to-Asset Matching Service.

Compares CVE affected-CPE patterns against the software
inventory in the database.  When matches are found, creates
``Alert`` records and updates asset risk scores.
"""
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from tip.core.logger import get_logger
from tip.core.models import Alert, Asset, CVE, Software

logger = get_logger(__name__)

SEVERITY_PRIORITY = {
    "CRITICAL": 1,
    "HIGH": 2,
    "MEDIUM": 3,
    "LOW": 4,
    "INFO": 5,
    "UNKNOWN": 5,
}


class MatchingService:
    """Match CVEs against asset software inventory via CPE comparison."""

    def __init__(self, db: Session):
        self.db = db

    # ── public API ───────────────────────────────────────────────

    def match_cve_to_assets(self, cve: CVE) -> List[Tuple[Asset, str]]:
        """
        Find all assets whose installed software matches a CVE's
        affected CPE patterns.

        Returns:
            List of (asset, matched_cpe_string) tuples.
        """
        if not cve.affected_cpe:
            return []

        matches: List[Tuple[Asset, str]] = []
        all_software = self.db.query(Software).filter(Software.cpe.isnot(None)).all()

        for sw in all_software:
            for vuln_cpe in cve.affected_cpe:
                if self.cpe_matches(sw.cpe, vuln_cpe):
                    for asset in sw.assets:
                        matches.append((asset, sw.cpe))
                        logger.info(
                            "CVE %s matches asset %s via %s %s",
                            cve.cve_id,
                            asset.hostname or asset.ip_address,
                            sw.name,
                            sw.version,
                        )
        return matches

    def scan_all_assets_for_cve(self, cve: CVE) -> List[Alert]:
        """
        Match a single CVE against all assets and create alerts
        for each match.
        """
        matches = self.match_cve_to_assets(cve)
        alerts: List[Alert] = []

        for asset, matched_cpe in matches:
            # deduplicate
            existing = (
                self.db.query(Alert)
                .filter(Alert.asset_id == asset.id, Alert.cve_id == cve.id)
                .first()
            )
            if existing:
                continue

            alert = Alert(
                source_module="vuln_intel",
                alert_type="cve_match",
                severity=cve.severity or "UNKNOWN",
                priority=SEVERITY_PRIORITY.get((cve.severity or "").upper(), 5),
                title=f"{cve.cve_id} affects {asset.hostname or asset.ip_address}",
                description=(
                    f"Vulnerability {cve.cve_id} (CVSS {cve.cvss_v3_score}) "
                    f"affects asset {asset.hostname or asset.ip_address}"
                    f"{':' + str(asset.port) if asset.port else ''}. "
                    f"Matched CPE: {matched_cpe}"
                ),
                raw_data={
                    "cve_id": cve.cve_id,
                    "cvss_score": cve.cvss_v3_score,
                    "matched_cpe": matched_cpe,
                    "asset_hostname": asset.hostname,
                    "asset_ip": asset.ip_address,
                },
                asset_id=asset.id,
                cve_id=cve.id,
            )
            self.db.add(alert)
            alerts.append(alert)

            # Update risk score (keep the highest)
            if cve.cvss_v3_score and cve.cvss_v3_score > (asset.risk_score or 0):
                asset.risk_score = cve.cvss_v3_score

        self.db.commit()
        return alerts

    def scan_new_cves_against_inventory(self, cves: List[CVE]) -> List[Alert]:
        """
        Batch process: match a list of new CVEs against all asset
        software and generate alerts.
        """
        all_alerts: List[Alert] = []
        for cve in cves:
            try:
                alerts = self.scan_all_assets_for_cve(cve)
                all_alerts.extend(alerts)
            except Exception as exc:
                logger.error("Error matching CVE %s: %s", cve.cve_id, exc)
        logger.info(
            "Scanned %d CVEs → %d alerts generated", len(cves), len(all_alerts)
        )
        return all_alerts

    # ── CPE matching logic ───────────────────────────────────────

    @staticmethod
    def cpe_matches(installed_cpe: str, vulnerable_cpe: str) -> bool:
        """
        Compare an installed CPE against a vulnerable CPE pattern.

        Both strings are expected in CPE 2.3 format:
            cpe:2.3:<part>:<vendor>:<product>:<version>:…

        The vulnerable CPE may use ``*`` as a wildcard for any field.
        """
        if not installed_cpe or not vulnerable_cpe:
            return False

        inst_parts = installed_cpe.lower().split(":")
        vuln_parts = vulnerable_cpe.lower().split(":")

        # Compare overlapping fields (vendor, product, version, …)
        for inst, vuln in zip(inst_parts, vuln_parts):
            if vuln == "*" or vuln == "-":
                continue
            if inst != vuln:
                return False

        return True
