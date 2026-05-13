"""
Unit tests for the CISA KEV Collector.
"""
import pytest
from unittest.mock import patch, MagicMock

from tip.core.models import CVE
from tip.modules.vuln_intel.collectors.kev_collector import KEVCollector
from tip.tests.fixtures.nvd_responses import CISA_KEV_RESPONSE


class TestKEVFetch:
    """Test KEV catalog download."""

    @patch("tip.modules.vuln_intel.collectors.kev_collector.requests.get")
    def test_fetch_kev_catalog(self, mock_get, db_session):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: CISA_KEV_RESPONSE,
            raise_for_status=lambda: None,
        )
        kev = KEVCollector(db_session)
        entries = kev.fetch_kev_catalog()
        assert len(entries) == 2

    @patch("tip.modules.vuln_intel.collectors.kev_collector.requests.get")
    def test_get_kev_cve_ids(self, mock_get, db_session):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: CISA_KEV_RESPONSE,
            raise_for_status=lambda: None,
        )
        kev = KEVCollector(db_session)
        ids = kev.get_kev_cve_ids()
        assert "CVE-2026-0001" in ids
        assert "CVE-2025-9999" in ids
        assert len(ids) == 2


class TestKEVMark:
    """Test marking CVEs as in the KEV catalog."""

    @patch("tip.modules.vuln_intel.collectors.kev_collector.requests.get")
    def test_mark_kev_cves(self, mock_get, db_session):
        # Pre-seed a CVE that's in the KEV list
        cve = CVE(
            cve_id="CVE-2026-0001",
            severity="CRITICAL",
            cvss_v3_score=9.8,
            is_in_cisa_kev=False,
            has_exploit=False,
        )
        db_session.add(cve)
        db_session.flush()

        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: CISA_KEV_RESPONSE,
            raise_for_status=lambda: None,
        )

        kev = KEVCollector(db_session)
        count = kev.mark_kev_cves()

        assert count == 1
        assert cve.is_in_cisa_kev is True
        assert cve.has_exploit is True

    @patch("tip.modules.vuln_intel.collectors.kev_collector.requests.get")
    def test_mark_kev_no_matching_cves(self, mock_get, db_session):
        # No CVEs in DB that match KEV
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: CISA_KEV_RESPONSE,
            raise_for_status=lambda: None,
        )
        kev = KEVCollector(db_session)
        count = kev.mark_kev_cves()
        assert count == 0

    @patch("tip.modules.vuln_intel.collectors.kev_collector.requests.get")
    def test_mark_kev_already_marked(self, mock_get, db_session):
        cve = CVE(
            cve_id="CVE-2026-0001",
            severity="CRITICAL",
            is_in_cisa_kev=True,  # already marked
            has_exploit=True,
        )
        db_session.add(cve)
        db_session.flush()

        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: CISA_KEV_RESPONSE,
            raise_for_status=lambda: None,
        )

        kev = KEVCollector(db_session)
        count = kev.mark_kev_cves()
        assert count == 0  # nothing new to mark
