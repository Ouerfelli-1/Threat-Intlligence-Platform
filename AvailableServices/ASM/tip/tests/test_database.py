"""
Unit tests for the TIP database models and relationships.
"""
import pytest
from datetime import datetime, timezone

from tip.core.models import (
    Organization, Asset, Software, CVE, DataLeak,
    Alert, WazuhEvent, CorrelationResult,
    asset_software, asset_cve,
)


class TestOrganization:
    """Tests for the Organization model."""

    def test_create_organization(self, db_session):
        org = Organization(name="Test Corp", primary_domain="test.com")
        db_session.add(org)
        db_session.flush()
        assert org.id is not None
        assert org.name == "Test Corp"
        assert org.primary_domain == "test.com"

    def test_org_unique_domain(self, db_session):
        org1 = Organization(name="Corp A", primary_domain="same.com")
        db_session.add(org1)
        db_session.flush()
        org2 = Organization(name="Corp B", primary_domain="same.com")
        db_session.add(org2)
        with pytest.raises(Exception):
            db_session.flush()

    def test_org_assets_relationship(self, db_session, sample_org, sample_asset):
        assert len(sample_org.assets) == 1
        assert sample_org.assets[0].hostname == "www.example.com"

    def test_org_leaks_relationship(self, db_session, sample_org, sample_leak):
        assert len(sample_org.leaks) == 1
        assert sample_org.leaks[0].leak_type == "credentials"


class TestAsset:
    """Tests for the Asset model."""

    def test_create_asset(self, db_session, sample_org):
        asset = Asset(
            organization_id=sample_org.id,
            asset_type="domain",
            hostname="api.example.com",
            is_active=True,
        )
        db_session.add(asset)
        db_session.flush()
        assert asset.id is not None
        assert asset.asset_type == "domain"

    def test_asset_risk_score_default(self, db_session, sample_asset):
        assert sample_asset.risk_score == 0.0

    def test_asset_technologies_json(self, db_session, sample_asset):
        assert "nginx" in sample_asset.technologies
        assert "wordpress" in sample_asset.technologies


class TestSoftware:
    """Tests for the Software model and M2M relationship."""

    def test_create_software(self, db_session):
        sw = Software(name="nginx", version="1.20.1", cpe="cpe:2.3:a:*:nginx:1.20.1:*:*:*:*:*:*:*")
        db_session.add(sw)
        db_session.flush()
        assert sw.id is not None

    def test_m2m_asset_software(self, db_session, sample_asset, sample_software):
        assert sample_software in sample_asset.software
        assert sample_asset in sample_software.assets


class TestCVE:
    """Tests for the CVE model and M2M relationship."""

    def test_create_cve(self, db_session, sample_cve):
        assert sample_cve.cve_id == "CVE-2026-0001"
        assert sample_cve.severity == "CRITICAL"
        assert sample_cve.cvss_v3_score == 9.8

    def test_unique_cve_id(self, db_session, sample_cve):
        dup = CVE(cve_id="CVE-2026-0001", description="Duplicate")
        db_session.add(dup)
        with pytest.raises(Exception):
            db_session.flush()

    def test_m2m_asset_cve(self, db_session, sample_asset, sample_cve):
        sample_asset.vulnerabilities.append(sample_cve)
        db_session.flush()
        assert sample_cve in sample_asset.vulnerabilities
        assert sample_asset in sample_cve.affected_assets


class TestDataLeak:
    """Tests for the DataLeak model."""

    def test_create_leak(self, db_session, sample_leak):
        assert sample_leak.leak_type == "credentials"
        assert sample_leak.contains_passwords is True
        assert sample_leak.record_count == 1500

    def test_leak_org_relationship(self, db_session, sample_leak, sample_org):
        assert sample_leak.organization.primary_domain == "example.com"


class TestAlert:
    """Tests for the unified Alert model."""

    def test_create_alert(self, db_session, sample_asset):
        alert = Alert(
            source_module="vuln_intel",
            alert_type="cve_match",
            severity="HIGH",
            title="Test alert",
            asset_id=sample_asset.id,
        )
        db_session.add(alert)
        db_session.flush()
        assert alert.id is not None
        assert alert.status == "open"

    def test_alert_asset_relationship(self, db_session, sample_asset):
        alert = Alert(
            source_module="ids",
            alert_type="wazuh_alert",
            severity="MEDIUM",
            title="IDS detection",
            asset_id=sample_asset.id,
        )
        db_session.add(alert)
        db_session.flush()
        assert alert.asset.hostname == "www.example.com"
        assert alert in sample_asset.alerts


class TestWazuhEvent:
    """Tests for WazuhEvent model."""

    def test_create_event(self, db_session):
        ev = WazuhEvent(
            wazuh_id="test-001",
            rule_id=5710,
            rule_level=10,
            rule_description="SSH brute force",
            agent_id="001",
        )
        db_session.add(ev)
        db_session.flush()
        assert ev.id is not None

    def test_unique_wazuh_id(self, db_session):
        ev1 = WazuhEvent(wazuh_id="dup-001", rule_id=1, rule_level=7)
        db_session.add(ev1)
        db_session.flush()
        ev2 = WazuhEvent(wazuh_id="dup-001", rule_id=2, rule_level=8)
        db_session.add(ev2)
        with pytest.raises(Exception):
            db_session.flush()


class TestCorrelationResult:
    """Tests for CorrelationResult model."""

    def test_create_result(self, db_session, sample_org):
        cr = CorrelationResult(
            organization_id=sample_org.id,
            rule_name="org_risk_score",
            risk_score=65.0,
            details={"total_cves": 5, "critical_cves": 2},
        )
        db_session.add(cr)
        db_session.flush()
        assert cr.id is not None
        assert cr.risk_score == 65.0
