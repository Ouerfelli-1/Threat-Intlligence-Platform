"""
Unit tests for the Wazuh REST API client.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone

from tip.core.integrations.wazuh_client import WazuhClient
from tip.tests.fixtures.wazuh_responses import (
    AUTH_RESPONSE,
    AGENTS_RESPONSE,
    PACKAGES_AGENT_001,
    OS_AGENT_001,
    PORTS_AGENT_001,
    ALERTS_RESPONSE,
    VULNERABILITIES_AGENT_001,
)


@pytest.fixture
def wazuh():
    return WazuhClient(
        base_url="https://mock-wazuh:55000",
        username="wazuh",
        password="wazuh",
        verify_ssl=False,
    )


class TestWazuhAuthentication:
    """Test JWT authentication and token caching."""

    @patch("tip.core.integrations.wazuh_client.requests.post")
    def test_authenticate_success(self, mock_post, wazuh):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: AUTH_RESPONSE,
            raise_for_status=lambda: None,
        )
        token = wazuh.authenticate()
        assert token == AUTH_RESPONSE["data"]["token"]
        mock_post.assert_called_once()

    @patch("tip.core.integrations.wazuh_client.requests.post")
    def test_token_caching(self, mock_post, wazuh):
        """Second call should reuse the cached token."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: AUTH_RESPONSE,
            raise_for_status=lambda: None,
        )
        wazuh.authenticate()
        wazuh.authenticate()
        # Only one HTTP call should be made
        mock_post.assert_called_once()

    @patch("tip.core.integrations.wazuh_client.requests.post")
    def test_token_refresh_on_expiry(self, mock_post, wazuh):
        """After token expires, a new one should be fetched."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: AUTH_RESPONSE,
            raise_for_status=lambda: None,
        )
        wazuh.authenticate()
        # Force token expiry
        wazuh._token_expires = datetime.now(timezone.utc) - timedelta(seconds=10)
        wazuh.authenticate()
        assert mock_post.call_count == 2


class TestWazuhAgents:
    """Test agent discovery methods."""

    @patch("tip.core.integrations.wazuh_client.requests.request")
    @patch("tip.core.integrations.wazuh_client.requests.post")
    def test_get_agents(self, mock_post, mock_request, wazuh):
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: AUTH_RESPONSE, raise_for_status=lambda: None
        )
        mock_request.return_value = MagicMock(
            status_code=200, json=lambda: AGENTS_RESPONSE, raise_for_status=lambda: None
        )
        agents = wazuh.get_agents()
        assert len(agents) == 3
        assert agents[0]["id"] == "001"
        assert agents[0]["name"] == "ubuntu-web"

    @patch("tip.core.integrations.wazuh_client.requests.request")
    @patch("tip.core.integrations.wazuh_client.requests.post")
    def test_get_agent_by_ip(self, mock_post, mock_request, wazuh):
        single_agent = {
            "data": {"affected_items": [AGENTS_RESPONSE["data"]["affected_items"][0]]}
        }
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: AUTH_RESPONSE, raise_for_status=lambda: None
        )
        mock_request.return_value = MagicMock(
            status_code=200, json=lambda: single_agent, raise_for_status=lambda: None
        )
        agent = wazuh.get_agent_by_ip("10.0.1.10")
        assert agent["name"] == "ubuntu-web"

    @patch("tip.core.integrations.wazuh_client.requests.request")
    @patch("tip.core.integrations.wazuh_client.requests.post")
    def test_get_agent_by_ip_not_found(self, mock_post, mock_request, wazuh):
        empty = {"data": {"affected_items": []}}
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: AUTH_RESPONSE, raise_for_status=lambda: None
        )
        mock_request.return_value = MagicMock(
            status_code=200, json=lambda: empty, raise_for_status=lambda: None
        )
        assert wazuh.get_agent_by_ip("99.99.99.99") is None


class TestWazuhSyscollector:
    """Test Syscollector endpoints."""

    @patch("tip.core.integrations.wazuh_client.requests.request")
    @patch("tip.core.integrations.wazuh_client.requests.post")
    def test_get_agent_packages(self, mock_post, mock_request, wazuh):
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: AUTH_RESPONSE, raise_for_status=lambda: None
        )
        mock_request.return_value = MagicMock(
            status_code=200, json=lambda: PACKAGES_AGENT_001, raise_for_status=lambda: None
        )
        pkgs = wazuh.get_agent_packages("001")
        assert len(pkgs) == 6
        names = [p["name"] for p in pkgs]
        assert "apache2" in names
        assert "openssl" in names

    @patch("tip.core.integrations.wazuh_client.requests.request")
    @patch("tip.core.integrations.wazuh_client.requests.post")
    def test_get_agent_os(self, mock_post, mock_request, wazuh):
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: AUTH_RESPONSE, raise_for_status=lambda: None
        )
        mock_request.return_value = MagicMock(
            status_code=200, json=lambda: OS_AGENT_001, raise_for_status=lambda: None
        )
        os_info = wazuh.get_agent_os("001")
        assert os_info["os_name"] == "Ubuntu"

    @patch("tip.core.integrations.wazuh_client.requests.request")
    @patch("tip.core.integrations.wazuh_client.requests.post")
    def test_get_agent_ports(self, mock_post, mock_request, wazuh):
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: AUTH_RESPONSE, raise_for_status=lambda: None
        )
        mock_request.return_value = MagicMock(
            status_code=200, json=lambda: PORTS_AGENT_001, raise_for_status=lambda: None
        )
        ports = wazuh.get_agent_ports("001")
        assert len(ports) == 3


class TestWazuhAlerts:
    """Test alert retrieval."""

    @patch("tip.core.integrations.wazuh_client.requests.request")
    @patch("tip.core.integrations.wazuh_client.requests.post")
    def test_get_alerts(self, mock_post, mock_request, wazuh):
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: AUTH_RESPONSE, raise_for_status=lambda: None
        )
        mock_request.return_value = MagicMock(
            status_code=200, json=lambda: ALERTS_RESPONSE, raise_for_status=lambda: None
        )
        alerts = wazuh.get_alerts(level_min=7)
        assert len(alerts) == 4
        # Verify highest level is present
        levels = [a["rule"]["level"] for a in alerts]
        assert 15 in levels

    @patch("tip.core.integrations.wazuh_client.requests.request")
    @patch("tip.core.integrations.wazuh_client.requests.post")
    def test_get_agent_vulnerabilities(self, mock_post, mock_request, wazuh):
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: AUTH_RESPONSE, raise_for_status=lambda: None
        )
        mock_request.return_value = MagicMock(
            status_code=200, json=lambda: VULNERABILITIES_AGENT_001, raise_for_status=lambda: None
        )
        vulns = wazuh.get_agent_vulnerabilities("001")
        assert len(vulns) == 2
        cve_ids = [v["cve"] for v in vulns]
        assert "CVE-2023-25690" in cve_ids
