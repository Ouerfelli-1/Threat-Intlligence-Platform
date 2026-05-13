"""
Unit tests for the Recon Findings API client.
"""
import pytest
from unittest.mock import patch, MagicMock

from tip.core.integrations.recon_client import ReconClient
from tip.tests.fixtures.recon_responses import (
    SCOPE_SUBDOMAINS_RESPONSE,
    SCOPE_FINDINGS_RESPONSE,
    SCOPE_CVES_RESPONSE,
    SCOPE_SERVICES_RESPONSE,
    SEARCH_RESPONSE,
)


@pytest.fixture
def recon():
    return ReconClient(base_url="http://mock-recon:8001")


class TestReconSubdomains:
    """Test subdomain retrieval."""

    @patch("tip.core.integrations.recon_client.requests.get")
    def test_get_scope_subdomains(self, mock_get, recon):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: SCOPE_SUBDOMAINS_RESPONSE,
            raise_for_status=lambda: None,
        )
        result = recon.get_scope_subdomains("scope-uuid-001")
        subs = result["subdomains"]
        assert len(subs) == 4
        values = [s["value"] for s in subs]
        assert "www.example.com" in values
        assert "api.example.com" in values


class TestReconFindings:
    """Test generic findings retrieval."""

    @patch("tip.core.integrations.recon_client.requests.get")
    def test_get_scope_findings(self, mock_get, recon):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: SCOPE_FINDINGS_RESPONSE,
            raise_for_status=lambda: None,
        )
        result = recon.get_scope_findings("scope-uuid-001")
        assert result["total"] == 6
        assert len(result["findings"]) == 6

    @patch("tip.core.integrations.recon_client.requests.get")
    def test_get_scope_findings_types(self, mock_get, recon):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: SCOPE_FINDINGS_RESPONSE,
            raise_for_status=lambda: None,
        )
        result = recon.get_scope_findings("scope-uuid-001")
        types = {f["finding_type"] for f in result["findings"]}
        assert "subdomain" in types
        assert "port" in types
        assert "technology" in types


class TestReconCVEs:
    """Test CVE retrieval from recon."""

    @patch("tip.core.integrations.recon_client.requests.get")
    def test_get_scope_cves(self, mock_get, recon):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: SCOPE_CVES_RESPONSE,
            raise_for_status=lambda: None,
        )
        result = recon.get_scope_cves("scope-uuid-001")
        assert len(result["cves"]) == 1
        assert result["cves"][0]["value"] == "CVE-2023-44487"


class TestReconServices:
    """Test service retrieval."""

    @patch("tip.core.integrations.recon_client.requests.get")
    def test_get_scope_services(self, mock_get, recon):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: SCOPE_SERVICES_RESPONSE,
            raise_for_status=lambda: None,
        )
        result = recon.get_scope_services("scope-uuid-001")
        services = result["services"]
        assert len(services) == 3
        ports = [s["port"] for s in services]
        assert 443 in ports
        assert 80 in ports
        assert 22 in ports


class TestReconSearch:
    """Test search endpoint."""

    @patch("tip.core.integrations.recon_client.requests.get")
    def test_search(self, mock_get, recon):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: SEARCH_RESPONSE,
            raise_for_status=lambda: None,
        )
        result = recon.search("www.example.com")
        assert result["total"] == 1
        assert result["results"][0]["value"] == "www.example.com"


class TestReconPorts:
    """Test ports endpoint."""

    @patch("tip.core.integrations.recon_client.requests.get")
    def test_get_scope_ports(self, mock_get, recon):
        ports_resp = {
            "ports": [
                {"hostname": "www.example.com", "ip": "93.184.216.34", "port": 443},
                {"hostname": "www.example.com", "ip": "93.184.216.34", "port": 80},
            ]
        }
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: ports_resp,
            raise_for_status=lambda: None,
        )
        result = recon.get_scope_ports("scope-uuid-001")
        assert len(result["ports"]) == 2
