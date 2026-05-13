"""
Correlation Engine.

Runs cross-module correlation rules and generates combined alerts that
represent higher-order threats (e.g. critical CVE on an exposed asset
that also appears in a data leak).
"""
from typing import Dict, List

from sqlalchemy.orm import Session

from tip.core.logger import get_logger
from tip.core.models import Alert, CorrelationResult, Organization
from tip.correlation.rules.cve_exposed import CVEExposedRule
from tip.correlation.rules.leak_login import LeakLoginRule
from tip.correlation.rules.combined_risk import CombinedRiskRule

logger = get_logger(__name__)


class CorrelationEngine:
    """Orchestrates all correlation rules for an organization."""

    def __init__(self, db: Session):
        self.db = db
        self.rules = [
            CVEExposedRule(db),
            LeakLoginRule(db),
            CombinedRiskRule(db),
        ]

    # ── public API ───────────────────────────────────────────────

    def run_all(self, org: Organization) -> List[Alert]:
        """Execute every rule and return the new alerts they generate."""
        all_alerts: List[Alert] = []
        for rule in self.rules:
            try:
                alerts = rule.evaluate(org)
                all_alerts.extend(alerts)
                logger.info(
                    "Rule %-30s → %d alert(s) for org %s",
                    rule.name, len(alerts), org.primary_domain,
                )
            except Exception:
                logger.exception("Rule %s failed for org %s", rule.name, org.primary_domain)
        return all_alerts

    def calculate_org_risk_score(self, org: Organization) -> Dict:
        """
        Compute an organization-level risk score (0-100) from all data.
        """
        assets = [a for a in org.assets if a.is_active]

        total_cves = 0
        critical_cves = 0
        exposed_assets = 0
        total_leaks = len(org.leaks)

        for asset in assets:
            total_cves += len(asset.vulnerabilities)
            critical_cves += sum(
                1 for c in asset.vulnerabilities if c.severity == "CRITICAL"
            )
            if asset.port and asset.port in (80, 443, 8080, 8443, 22, 3389):
                exposed_assets += 1

        score = min(
            100,
            (critical_cves * 10)
            + (total_cves * 2)
            + (total_leaks * 15)
            + (exposed_assets * 5),
        )

        result = CorrelationResult(
            organization_id=org.id,
            rule_name="org_risk_score",
            risk_score=score,
            details={
                "total_assets": len(assets),
                "exposed_assets": exposed_assets,
                "total_cves": total_cves,
                "critical_cves": critical_cves,
                "data_leaks": total_leaks,
            },
        )
        self.db.add(result)
        self.db.commit()

        return {
            "organization": org.name,
            "domain": org.primary_domain,
            "risk_score": score,
            "risk_level": _score_to_level(score),
            "metrics": result.details,
        }


# ── helpers ──────────────────────────────────────────────────────

def _score_to_level(score: float) -> str:
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    if score >= 20:
        return "LOW"
    return "INFO"
