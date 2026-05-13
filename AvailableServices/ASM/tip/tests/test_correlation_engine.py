"""
Unit tests for the Correlation Engine and all three correlation rules.
"""
import pytest
from datetime import datetime, timedelta, timezone

from tip.core.models import (
    Alert, Asset, CVE, DataLeak, Organization,
    CorrelationResult, WazuhEvent,
)
from tip.correlation.engine import CorrelationEngine
from tip.correlation.rules.cve_exposed import CVEExposedRule
from tip.correlation.rules.leak_login import LeakLoginRule
from tip.correlation.rules.combined_risk import CombinedRiskRule


# ── CVE Exposed Rule ─────────────────────────────────────────────

class TestCVEExposedRule:
    """Critical CVE + exposed port correlation."""

    def _setup(self, db_session, sample_org):
        """Create an exposed asset with a critical CVE."""
        asset = Asset(
            organization_id=sample_org.id, asset_type="service",
            hostname="web.example.com", ip_address="10.0.0.1",
            port=443, is_active=True, risk_score=9.8,
        )
        db_session.add(asset)
        db_session.flush()

        cve = CVE(
            cve_id="CVE-2026-CORR01", severity="CRITICAL",
            cvss_v3_score=9.8,
        )
        db_session.add(cve)
        db_session.flush()
        asset.vulnerabilities.append(cve)
        db_session.flush()
        return asset, cve

    def test_fires_on_critical_exposed(self, db_session, sample_org):
        asset, cve = self._setup(db_session, sample_org)
        rule = CVEExposedRule(db_session)
        alerts = rule.evaluate(sample_org)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "correlation_critical_exposed"
        assert alerts[0].severity == "CRITICAL"
        assert alerts[0].asset_id == asset.id

    def test_skips_non_exposed_port(self, db_session, sample_org):
        asset, cve = self._setup(db_session, sample_org)
        asset.port = 5432  # database port, not in exposed list
        db_session.flush()
        rule = CVEExposedRule(db_session)
        alerts = rule.evaluate(sample_org)
        assert len(alerts) == 0

    def test_skips_low_risk_score(self, db_session, sample_org):
        asset, cve = self._setup(db_session, sample_org)
        asset.risk_score = 5.0
        db_session.flush()
        rule = CVEExposedRule(db_session)
        alerts = rule.evaluate(sample_org)
        assert len(alerts) == 0

    def test_deduplicates_within_24h(self, db_session, sample_org):
        self._setup(db_session, sample_org)
        rule = CVEExposedRule(db_session)
        alerts1 = rule.evaluate(sample_org)
        alerts2 = rule.evaluate(sample_org)
        assert len(alerts1) == 1
        assert len(alerts2) == 0


# ── Leak Login Rule ──────────────────────────────────────────────

class TestLeakLoginRule:
    """Data leak + active login service correlation."""

    def _setup(self, db_session, sample_org):
        asset = Asset(
            organization_id=sample_org.id, asset_type="service",
            hostname="www.example.com", ip_address="10.0.0.1",
            port=443, is_active=True,
            technologies=["wordpress", "nginx"],
        )
        db_session.add(asset)
        db_session.flush()

        leak = DataLeak(
            organization_id=sample_org.id,
            leak_source="DarkMarket",
            leak_type="credentials",
            contains_passwords=True,
            affected_domains=["example.com", "www.example.com"],
            record_count=1500,
            severity="HIGH",
        )
        db_session.add(leak)
        db_session.flush()
        return asset, leak

    def test_fires_on_leak_with_login(self, db_session, sample_org):
        asset, leak = self._setup(db_session, sample_org)
        rule = LeakLoginRule(db_session)
        alerts = rule.evaluate(sample_org)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "correlation_leak_login"
        assert alerts[0].asset_id == asset.id
        assert alerts[0].leak_id == leak.id

    def test_skips_no_password_leak(self, db_session, sample_org):
        asset, leak = self._setup(db_session, sample_org)
        leak.contains_passwords = False
        db_session.flush()
        rule = LeakLoginRule(db_session)
        alerts = rule.evaluate(sample_org)
        assert len(alerts) == 0

    def test_skips_non_web_asset(self, db_session, sample_org):
        asset, leak = self._setup(db_session, sample_org)
        asset.technologies = ["ssh"]
        asset.port = 5432  # not a web port
        db_session.flush()
        rule = LeakLoginRule(db_session)
        alerts = rule.evaluate(sample_org)
        assert len(alerts) == 0

    def test_skips_unmatched_domain(self, db_session, sample_org):
        asset, leak = self._setup(db_session, sample_org)
        leak.affected_domains = ["other.com"]
        db_session.flush()
        rule = LeakLoginRule(db_session)
        alerts = rule.evaluate(sample_org)
        assert len(alerts) == 0


# ── Combined Risk Rule ───────────────────────────────────────────

class TestCombinedRiskRule:
    """Multi-vector risk correlation."""

    def test_fires_with_two_vectors(self, db_session, sample_org):
        """CVE + exposed port = 2 vectors."""
        asset = Asset(
            organization_id=sample_org.id, asset_type="service",
            hostname="multi.example.com", ip_address="10.0.0.2",
            port=443, is_active=True, risk_score=9.0,
        )
        db_session.add(asset)
        db_session.flush()

        cve = CVE(cve_id="CVE-2026-COMB01", severity="CRITICAL", cvss_v3_score=9.0)
        db_session.add(cve)
        db_session.flush()
        asset.vulnerabilities.append(cve)
        db_session.flush()

        rule = CombinedRiskRule(db_session)
        alerts = rule.evaluate(sample_org)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "correlation_combined_risk"

    def test_skips_single_vector(self, db_session, sample_org):
        """Exposed port only = 1 vector → no alert."""
        asset = Asset(
            organization_id=sample_org.id, asset_type="service",
            hostname="single.example.com", ip_address="10.0.0.3",
            port=443, is_active=True, risk_score=8.0,
        )
        db_session.add(asset)
        db_session.flush()
        # No CVE, no leak, no IDS → only exposed port
        rule = CombinedRiskRule(db_session)
        alerts = rule.evaluate(sample_org)
        assert len(alerts) == 0

    def test_three_vectors(self, db_session, sample_org):
        """CVE + IDS + exposed port = 3 vectors."""
        asset = Asset(
            organization_id=sample_org.id, asset_type="service",
            hostname="critical.example.com", ip_address="10.0.0.4",
            port=80, is_active=True, risk_score=9.5,
            wazuh_agent_id="005",
        )
        db_session.add(asset)
        db_session.flush()

        cve = CVE(cve_id="CVE-2026-COMB03", severity="HIGH", cvss_v3_score=8.5)
        db_session.add(cve)
        db_session.flush()
        asset.vulnerabilities.append(cve)

        ev = WazuhEvent(
            wazuh_id="ids-comb-001", rule_id=5710, rule_level=12,
            agent_id="005",
        )
        db_session.add(ev)
        db_session.flush()

        rule = CombinedRiskRule(db_session)
        alerts = rule.evaluate(sample_org)
        assert len(alerts) == 1
        raw = alerts[0].raw_data
        assert len(raw["risk_factors"]) == 3


# ── Correlation Engine ───────────────────────────────────────────

class TestCorrelationEngine:
    """Test the orchestration engine."""

    def test_run_all_runs_every_rule(self, db_session, sample_org):
        engine = CorrelationEngine(db_session)
        # With no matching data, all rules should return empty
        alerts = engine.run_all(sample_org)
        assert isinstance(alerts, list)

    def test_calculate_org_risk_score(self, db_session, sample_org):
        # Add some risk data
        asset = Asset(
            organization_id=sample_org.id, asset_type="service",
            hostname="scored.example.com", port=443,
            is_active=True, risk_score=9.0,
        )
        db_session.add(asset)
        db_session.flush()

        cve = CVE(cve_id="CVE-2026-RS01", severity="CRITICAL", cvss_v3_score=9.0)
        db_session.add(cve)
        db_session.flush()
        asset.vulnerabilities.append(cve)

        leak = DataLeak(
            organization_id=sample_org.id,
            leak_source="test", severity="HIGH",
        )
        db_session.add(leak)
        db_session.flush()

        engine = CorrelationEngine(db_session)
        result = engine.calculate_org_risk_score(sample_org)

        assert result["risk_score"] > 0
        assert result["organization"] == "Example Corp"
        assert "risk_level" in result
        assert result["metrics"]["total_cves"] == 1
        assert result["metrics"]["critical_cves"] == 1
        assert result["metrics"]["data_leaks"] == 1

    def test_risk_score_capped_at_100(self, db_session, sample_org):
        """Even with extreme data, score should not exceed 100."""
        # Add lots of leaks to push score up
        for i in range(20):
            leak = DataLeak(
                organization_id=sample_org.id,
                leak_source=f"source_{i}",
                severity="CRITICAL",
            )
            db_session.add(leak)
        db_session.flush()

        engine = CorrelationEngine(db_session)
        result = engine.calculate_org_risk_score(sample_org)
        assert result["risk_score"] <= 100
