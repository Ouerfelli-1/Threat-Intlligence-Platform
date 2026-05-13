"""
Unit tests for the NVD CVE Collector.
"""
import pytest
from unittest.mock import patch, MagicMock

from tip.modules.vuln_intel.collectors.nvd_collector import NVDCollector
from tip.tests.fixtures.nvd_responses import (
    NVD_RECENT_CVES_RESPONSE,
    NVD_SINGLE_CVE_RESPONSE,
    NVD_EMPTY_RESPONSE,
)


@pytest.fixture
def collector():
    c = NVDCollector(api_key="")
    c.rate_limit = 0  # disable rate limiting in tests
    return c


class TestNVDFetch:
    """Test CVE fetching from NVD."""

    @patch("tip.modules.vuln_intel.collectors.nvd_collector.requests.get")
    def test_fetch_recent_cves(self, mock_get, collector):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: NVD_RECENT_CVES_RESPONSE,
            raise_for_status=lambda: None,
        )
        results = collector.fetch_recent_cves(days=7)
        assert len(results) == 3
        assert results[0]["cve"]["id"] == "CVE-2026-0001"

    @patch("tip.modules.vuln_intel.collectors.nvd_collector.requests.get")
    def test_fetch_cve_by_id(self, mock_get, collector):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: NVD_SINGLE_CVE_RESPONSE,
            raise_for_status=lambda: None,
        )
        result = collector.fetch_cve_by_id("CVE-2026-0001")
        assert result is not None
        assert result["cve"]["id"] == "CVE-2026-0001"

    @patch("tip.modules.vuln_intel.collectors.nvd_collector.requests.get")
    def test_fetch_cve_not_found(self, mock_get, collector):
        mock_get.return_value = MagicMock(status_code=404)
        result = collector.fetch_cve_by_id("CVE-9999-9999")
        assert result is None

    @patch("tip.modules.vuln_intel.collectors.nvd_collector.requests.get")
    def test_fetch_empty_response(self, mock_get, collector):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: NVD_EMPTY_RESPONSE,
            raise_for_status=lambda: None,
        )
        results = collector.fetch_recent_cves(days=1)
        assert results == []


class TestNVDParse:
    """Test CVE parsing logic."""

    def test_parse_critical_cve(self):
        raw = NVD_RECENT_CVES_RESPONSE["vulnerabilities"][0]
        parsed = NVDCollector.parse_cve(raw)

        assert parsed["cve_id"] == "CVE-2026-0001"
        assert parsed["cvss_v3_score"] == 9.8
        assert parsed["severity"] == "CRITICAL"
        assert "apache" in parsed["description"].lower()
        assert len(parsed["affected_cpe"]) == 1
        assert "apache:http_server" in parsed["affected_cpe"][0]

    def test_parse_medium_cve(self):
        raw = NVD_RECENT_CVES_RESPONSE["vulnerabilities"][1]
        parsed = NVDCollector.parse_cve(raw)

        assert parsed["cve_id"] == "CVE-2026-0002"
        assert parsed["cvss_v3_score"] == 5.3
        assert parsed["severity"] == "MEDIUM"

    def test_parse_cve_without_cvss(self):
        raw = NVD_RECENT_CVES_RESPONSE["vulnerabilities"][2]
        parsed = NVDCollector.parse_cve(raw)

        assert parsed["cve_id"] == "CVE-2026-0003"
        assert parsed["cvss_v3_score"] is None
        assert parsed["severity"] == "UNKNOWN"

    def test_parse_exploit_flag(self):
        raw_with_exploit = {
            "cve": {
                "id": "CVE-2026-EX01",
                "descriptions": [{"lang": "en", "value": "Test"}],
                "metrics": {},
                "configurations": [],
                "references": [
                    {"url": "https://exploit-db.com/123", "tags": ["Exploit"]},
                ],
            }
        }
        parsed = NVDCollector.parse_cve(raw_with_exploit)
        assert parsed["has_exploit"] is True
        assert len(parsed["exploit_references"]) == 1

    def test_parse_no_exploit(self):
        raw = NVD_RECENT_CVES_RESPONSE["vulnerabilities"][1]
        parsed = NVDCollector.parse_cve(raw)
        assert parsed["has_exploit"] is False


class TestNVDRateLimit:
    """Test rate limiting behavior."""

    def test_rate_limit_with_api_key(self):
        c = NVDCollector(api_key="some-key")
        assert c.rate_limit == 0.6

    def test_rate_limit_without_api_key(self):
        c = NVDCollector(api_key="")
        # Falls back to settings.NVD_RATE_LIMIT (default 6.0)
        assert c.rate_limit >= 6.0
