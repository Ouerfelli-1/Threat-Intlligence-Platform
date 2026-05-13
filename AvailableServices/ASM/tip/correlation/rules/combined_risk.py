"""
Correlation Rule: Combined Multi-Vector Risk.

Fires when a single asset accumulates risk from two or more independent
vectors (CVE, data-leak, IDS alert, exposed port).
"""
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy.orm import Session

from tip.core.logger import get_logger
from tip.core.models import Alert, Asset, DataLeak, Organization, WazuhEvent

logger = get_logger(__name__)


class CombinedRiskRule:
    name = "combined_multi_vector_risk"

    def __init__(self, db: Session):
        self.db = db

    def evaluate(self, org: Organization) -> List[Alert]:
        alerts: List[Alert] = []
        cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)

        risky_assets = (
            self.db.query(Asset)
            .filter(
                Asset.organization_id == org.id,
                Asset.is_active.is_(True),
                Asset.risk_score >= 7.0,
            )
            .all()
        )

        for asset in risky_assets:
            risk_factors: List[str] = []

            # 1. High/Critical CVEs
            high_cves = [
                c for c in asset.vulnerabilities
                if c.severity in ("CRITICAL", "HIGH")
            ]
            if high_cves:
                risk_factors.append(f"{len(high_cves)} HIGH/CRITICAL CVEs")

            # 2. Data leaks mentioning asset hostname
            if asset.hostname:
                leak_q = (
                    self.db.query(DataLeak)
                    .filter(DataLeak.organization_id == org.id)
                    .all()
                )
                matching_leaks = [
                    lk for lk in leak_q
                    if asset.hostname in (lk.affected_domains or [])
                ]
                if matching_leaks:
                    risk_factors.append(f"{len(matching_leaks)} data leak(s)")

            # 3. IDS alerts referencing this asset
            if asset.wazuh_agent_id:
                ids_count = (
                    self.db.query(WazuhEvent)
                    .filter(
                        WazuhEvent.agent_id == asset.wazuh_agent_id,
                        WazuhEvent.rule_level >= 10,
                    )
                    .count()
                )
                if ids_count > 0:
                    risk_factors.append(f"{ids_count} high-severity IDS alert(s)")

            # 4. Exposed service port
            if asset.port and asset.port in (80, 443, 22, 3389, 8080, 8443):
                risk_factors.append(f"exposed on port {asset.port}")

            # ── need at least 2 vectors ──
            if len(risk_factors) < 2:
                continue

            # deduplicate within 24 h
            existing = (
                self.db.query(Alert)
                .filter(
                    Alert.asset_id == asset.id,
                    Alert.alert_type == "correlation_combined_risk",
                    Alert.created_at >= cutoff_24h,
                )
                .first()
            )
            if existing:
                continue

            alert = Alert(
                source_module="correlation",
                alert_type="correlation_combined_risk",
                severity="CRITICAL",
                priority=1,
                title=(
                    f"Multi-vector risk: "
                    f"{asset.hostname or asset.ip_address}"
                ),
                description=(
                    f"Asset {asset.hostname} ({asset.ip_address}) has "
                    f"multiple risk factors: {'; '.join(risk_factors)}. "
                    f"Combined risk score: {asset.risk_score:.1f}. "
                    f"Prioritize for remediation."
                ),
                raw_data={
                    "asset_hostname": asset.hostname,
                    "risk_factors": risk_factors,
                    "risk_score": asset.risk_score,
                    "correlation_rule": self.name,
                },
                asset_id=asset.id,
            )
            self.db.add(alert)
            alerts.append(alert)

        self.db.commit()
        return alerts
