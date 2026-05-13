"""
Unit tests for the OpenCTI GraphQL API client.
"""
import pytest
from unittest.mock import patch, MagicMock

from tip.core.integrations.opencti_client import OpenCTIClient
from tip.tests.fixtures.opencti_responses import (
    CREATE_INDICATOR_RESPONSE,
    CREATE_VULNERABILITY_RESPONSE,
    CREATE_REPORT_RESPONSE,
    CREATE_RELATIONSHIP_RESPONSE,
)


@pytest.fixture
def opencti():
    return OpenCTIClient(
        base_url="http://mock-opencti:8080",
        api_key="test-opencti-key",
    )


class TestOpenCTIIndicator:
    """Test indicator creation."""

    @patch("tip.core.integrations.opencti_client.requests.post")
    def test_create_indicator(self, mock_post, opencti):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: CREATE_INDICATOR_RESPONSE,
            raise_for_status=lambda: None,
        )
        result = opencti.create_indicator(
            name="Malicious IP 203.0.113.42",
            pattern="[ipv4-addr:value = '203.0.113.42']",
            pattern_type="stix",
        )
        assert result["id"] == "indicator--aaa-bbb-ccc"
        assert result["name"] == "IP: 10.0.1.10"

    @patch("tip.core.integrations.opencti_client.requests.post")
    def test_search_indicators(self, mock_post, opencti):
        search_resp = {
            "data": {
                "indicators": {
                    "edges": [
                        {"node": {"id": "indicator--uuid-001", "name": "Test"}}
                    ]
                }
            }
        }
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: search_resp, raise_for_status=lambda: None
        )
        results = opencti.search_indicators("203.0.113.42")
        assert len(results) == 1


class TestOpenCTIVulnerability:
    """Test vulnerability creation."""

    @patch("tip.core.integrations.opencti_client.requests.post")
    def test_create_vulnerability(self, mock_post, opencti):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: CREATE_VULNERABILITY_RESPONSE,
            raise_for_status=lambda: None,
        )
        result = opencti.create_vulnerability(
            cve_id="CVE-2026-0001",
            description="Critical RCE in Apache",
        )
        assert result["id"] == "vulnerability--ddd-eee-fff"
        assert result["name"] == "CVE-2023-25690"


class TestOpenCTIReport:
    """Test report creation."""

    @patch("tip.core.integrations.opencti_client.requests.post")
    def test_create_report(self, mock_post, opencti):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: CREATE_REPORT_RESPONSE,
            raise_for_status=lambda: None,
        )
        result = opencti.create_report(
            name="TIP Alert Report",
            description="Test report from TIP",
            object_refs=["indicator--uuid-001"],
        )
        assert result["id"] == "report--111-222-333"

    @patch("tip.core.integrations.opencti_client.requests.post")
    def test_create_relationship(self, mock_post, opencti):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: CREATE_RELATIONSHIP_RESPONSE,
            raise_for_status=lambda: None,
        )
        result = opencti.create_relationship(
            from_id="indicator--uuid-001",
            to_id="vulnerability--uuid-001",
            relationship_type="indicates",
        )
        assert result["id"] == "relationship--xxx-yyy-zzz"


class TestOpenCTIHeaders:
    """Test that client sends correct headers."""

    @patch("tip.core.integrations.opencti_client.requests.post")
    def test_auth_header_sent(self, mock_post, opencti):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: CREATE_INDICATOR_RESPONSE,
            raise_for_status=lambda: None,
        )
        opencti.create_indicator(
            name="Test", pattern="[ipv4-addr:value = '1.2.3.4']", pattern_type="stix"
        )
        call_headers = mock_post.call_args[1].get("headers", {})
        assert "Authorization" in call_headers
        assert "test-opencti-key" in call_headers["Authorization"]
