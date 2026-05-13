"""
Unit tests for the CVE-to-Asset Matching Service.

This is the most critical module – it determines which assets are
vulnerable based on CPE pattern comparison.
"""
import pytest
from unittest.mock import MagicMock

from tip.core.models import Alert, Asset, CVE, Software
from tip.modules.vuln_intel.matching_service import MatchingService


class TestCPEMatching:
    """Test the static CPE comparison logic."""

    def test_exact_match(self):
        installed = "cpe:2.3:a:apache:http_server:2.4.52:*:*:*:*:*:*:*"
        vulnerable = "cpe:2.3:a:apache:http_server:2.4.52:*:*:*:*:*:*:*"
        assert MatchingService.cpe_matches(installed, vulnerable) is True

    def test_wildcard_version(self):
        installed = "cpe:2.3:a:apache:http_server:2.4.52:*:*:*:*:*:*:*"
        vulnerable = "cpe:2.3:a:apache:http_server:*:*:*:*:*:*:*:*"
        assert MatchingService.cpe_matches(installed, vulnerable) is True

    def test_wildcard_vendor(self):
        installed = "cpe:2.3:a:ubuntu_developers:apache2:2.4.52:*:*:*:*:*:*:*"
        vulnerable = "cpe:2.3:a:*:apache2:*:*:*:*:*:*:*:*"
        assert MatchingService.cpe_matches(installed, vulnerable) is True

    def test_different_product_no_match(self):
        installed = "cpe:2.3:a:apache:http_server:2.4.52:*:*:*:*:*:*:*"
        vulnerable = "cpe:2.3:a:apache:tomcat:9.0.0:*:*:*:*:*:*:*"
        assert MatchingService.cpe_matches(installed, vulnerable) is False

    def test_different_vendor_no_match(self):
        installed = "cpe:2.3:a:ubuntu:openssl:3.0.2:*:*:*:*:*:*:*"
        vulnerable = "cpe:2.3:a:redhat:openssl:3.0.2:*:*:*:*:*:*:*"
        assert MatchingService.cpe_matches(installed, vulnerable) is False

    def test_empty_cpe_no_match(self):
        assert MatchingService.cpe_matches("", "cpe:2.3:a:*:*:*") is False
        assert MatchingService.cpe_matches("cpe:2.3:a:*:*:*", "") is False
        assert MatchingService.cpe_matches(None, None) is False

    def test_dash_treated_as_wildcard(self):
        installed = "cpe:2.3:a:apache:http_server:2.4.52:*:*:*:*:*:*:*"
        vulnerable = "cpe:2.3:a:apache:http_server:-:*:*:*:*:*:*:*"
        assert MatchingService.cpe_matches(installed, vulnerable) is True

    def test_case_insensitive(self):
        installed = "cpe:2.3:a:Apache:HTTP_Server:2.4.52:*:*:*:*:*:*:*"
        vulnerable = "cpe:2.3:a:apache:http_server:*:*:*:*:*:*:*:*"
        assert MatchingService.cpe_matches(installed, vulnerable) is True


class TestMatchCVEToAssets:
    """Test finding assets affected by a given CVE."""

    def test_match_finds_vulnerable_asset(self, db_session, sample_org):
        # Create asset with software
        asset = Asset(
            organization_id=sample_org.id, asset_type="service",
            hostname="web.example.com", port=443, is_active=True,
        )
        db_session.add(asset)
        db_session.flush()

        sw = Software(
            name="apache2", version="2.4.52",
            cpe="cpe:2.3:a:apache:http_server:2.4.52:*:*:*:*:*:*:*",
        )
        db_session.add(sw)
        db_session.flush()
        asset.software.append(sw)
        db_session.flush()

        cve = CVE(
            cve_id="CVE-2026-M001", severity="CRITICAL", cvss_v3_score=9.8,
            affected_cpe=["cpe:2.3:a:apache:http_server:*:*:*:*:*:*:*:*"],
        )
        db_session.add(cve)
        db_session.flush()

        svc = MatchingService(db_session)
        matches = svc.match_cve_to_assets(cve)
        assert len(matches) == 1
        assert matches[0][0].hostname == "web.example.com"

    def test_no_match_different_product(self, db_session, sample_org):
        asset = Asset(
            organization_id=sample_org.id, asset_type="service",
            hostname="web.example.com", port=443, is_active=True,
        )
        db_session.add(asset)
        db_session.flush()

        sw = Software(
            name="nginx", version="1.20.1",
            cpe="cpe:2.3:a:nginx:nginx:1.20.1:*:*:*:*:*:*:*",
        )
        db_session.add(sw)
        db_session.flush()
        asset.software.append(sw)

        cve = CVE(
            cve_id="CVE-2026-M002", severity="HIGH",
            affected_cpe=["cpe:2.3:a:apache:http_server:*:*:*:*:*:*:*:*"],
        )
        db_session.add(cve)
        db_session.flush()

        svc = MatchingService(db_session)
        matches = svc.match_cve_to_assets(cve)
        assert len(matches) == 0

    def test_cve_with_no_affected_cpe(self, db_session):
        cve = CVE(cve_id="CVE-2026-M003", severity="LOW", affected_cpe=None)
        db_session.add(cve)
        db_session.flush()

        svc = MatchingService(db_session)
        matches = svc.match_cve_to_assets(cve)
        assert matches == []


class TestScanAndAlerts:
    """Test alert generation from CVE matching."""

    def _setup_match(self, db_session, sample_org):
        """Set up an asset+software+cve that will match."""
        asset = Asset(
            organization_id=sample_org.id, asset_type="service",
            hostname="victim.example.com", ip_address="10.0.0.5",
            port=443, is_active=True, risk_score=0.0,
        )
        db_session.add(asset)
        db_session.flush()

        sw = Software(
            name="openssl", version="3.0.2",
            cpe="cpe:2.3:a:openssl:openssl:3.0.2:*:*:*:*:*:*:*",
        )
        db_session.add(sw)
        db_session.flush()
        asset.software.append(sw)

        cve = CVE(
            cve_id="CVE-2026-SCAN01", severity="CRITICAL", cvss_v3_score=9.8,
            affected_cpe=["cpe:2.3:a:openssl:openssl:*:*:*:*:*:*:*:*"],
        )
        db_session.add(cve)
        db_session.flush()
        return asset, cve

    def test_scan_creates_alert(self, db_session, sample_org):
        asset, cve = self._setup_match(db_session, sample_org)
        svc = MatchingService(db_session)
        alerts = svc.scan_all_assets_for_cve(cve)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.source_module == "vuln_intel"
        assert alert.alert_type == "cve_match"
        assert alert.severity == "CRITICAL"
        assert alert.asset_id == asset.id
        assert alert.cve_id == cve.id

    def test_scan_updates_risk_score(self, db_session, sample_org):
        asset, cve = self._setup_match(db_session, sample_org)
        assert asset.risk_score == 0.0

        svc = MatchingService(db_session)
        svc.scan_all_assets_for_cve(cve)

        assert asset.risk_score == 9.8

    def test_scan_deduplicates_alerts(self, db_session, sample_org):
        asset, cve = self._setup_match(db_session, sample_org)
        svc = MatchingService(db_session)

        alerts1 = svc.scan_all_assets_for_cve(cve)
        alerts2 = svc.scan_all_assets_for_cve(cve)  # second run

        assert len(alerts1) == 1
        assert len(alerts2) == 0  # no duplicate

    def test_scan_batch(self, db_session, sample_org):
        asset, cve1 = self._setup_match(db_session, sample_org)
        cve2 = CVE(
            cve_id="CVE-2026-SCAN02", severity="HIGH", cvss_v3_score=7.5,
            affected_cpe=["cpe:2.3:a:openssl:openssl:*:*:*:*:*:*:*:*"],
        )
        db_session.add(cve2)
        db_session.flush()

        svc = MatchingService(db_session)
        all_alerts = svc.scan_new_cves_against_inventory([cve1, cve2])
        assert len(all_alerts) == 2
