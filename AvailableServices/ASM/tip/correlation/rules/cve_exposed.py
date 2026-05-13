"""
Correlation Rule: Critical CVE on an exposed asset.

Fires when an asset has a CVSS ≥ 9.0 vulnerability **and** is
internet-facing (port 80/443/8080/8443).
"""
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy.orm import Session

from tip.core.logger import get_logger
from tip.core.models import Alert, Asset, Organization

logger = get_logger(__name__)

_EXPOSED_PORTS = {80, 443, 8080, 8443, 22, 3389}


class CVEExposedRule:
    name = "cve_exposed_asset"

    def __init__(self, db: Session):
        self.db = db

    def evaluate(self, org: Organization) -> List[Alert]:
        alerts: List[Alert] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        # Find active assets with high risk score and exposed ports
        candidates = (
            self.db.query(Asset)
            .filter(
                Asset.organization_id == org.id,
                Asset.is_active.is_(True),
                Asset.risk_score >= 9.0,
            )
            .all()
        )

        for asset in candidates:
            if asset.port not in _EXPOSED_PORTS:
                continue

            critical_cves = [
                c for c in asset.vulnerabilities if c.severity == "CRITICAL"
            ]
            if not critical_cves:
                continue

            # deduplicate within 24 h
            existing = (
                self.db.query(Alert)
                .filter(
                    Alert.asset_id == asset.id,
                    Alert.alert_type == "correlation_critical_exposed",
                    Alert.created_at >= cutoff,
                )
                .first()
            )
            if existing:
                continue

            cve_list = ", ".join(c.cve_id for c in critical_cves[:5])
            alert = Alert(
                source_module="correlation",
                alert_type="correlation_critical_exposed",
                severity="CRITICAL",
                priority=1,
                title=(
                    f"CRITICAL: Exposed asset {asset.hostname or asset.ip_address} "
                    f"has {len(critical_cves)} critical CVE(s)"
                ),
                description=(
                    f"Asset {asset.hostname} ({asset.ip_address}:{asset.port}) "
                    f"is internet-exposed and has {len(critical_cves)} critical "
                    f"vulnerabilities: {cve_list}. IMMEDIATE ACTION REQUIRED."
                ),
                raw_data={
                    "asset_hostname": asset.hostname,
                    "asset_ip": asset.ip_address,
                    "asset_port": asset.port,
                    "cves": [c.cve_id for c in critical_cves],
                    "correlation_rule": self.name,
                },
                asset_id=asset.id,
            )
            self.db.add(alert)
            alerts.append(alert)

        self.db.commit()
        return alerts
