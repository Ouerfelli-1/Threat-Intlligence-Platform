"""
Unit tests for the MISP REST API client.
"""
import pytest
from unittest.mock import patch, MagicMock

from tip.core.integrations.misp_client import MISPClient
from tip.tests.fixtures.misp_responses import (
    CREATE_EVENT_RESPONSE,
    SEARCH_EVENTS_RESPONSE,
    ADD_ATTRIBUTE_RESPONSE,
    SEARCH_ATTRIBUTES_RESPONSE,
)


@pytest.fixture
def misp():
    return MISPClient(
        base_url="https://mock-misp",
        api_key="test-misp-key",
        verify_ssl=False,
    )


class TestMISPEvents:
    """Test event creation and search."""

    @patch("tip.core.integrations.misp_client.requests.post")
    def test_create_event(self, mock_post, misp):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: CREATE_EVENT_RESPONSE,
            raise_for_status=lambda: None,
        )
        result = misp.create_event(
            info="TIP Alert: Critical CVE",
            threat_level_id=1,
        )
        assert "Event" in result
        assert result["Event"]["id"] == "99"
        mock_post.assert_called_once()

    @patch("tip.core.integrations.misp_client.requests.post")
    def test_search_events(self, mock_post, misp):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: SEARCH_EVENTS_RESPONSE,
            raise_for_status=lambda: None,
        )
        events = misp.search_events("CVE-2026-0001")
        assert len(events) == 1
        assert events[0]["Event"]["info"] == "CVE-2023-25690 affects ubuntu-web"

    @patch("tip.core.integrations.misp_client.requests.post")
    def test_create_event_with_attributes(self, mock_post, misp):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: CREATE_EVENT_RESPONSE,
            raise_for_status=lambda: None,
        )
        attrs = [
            {"type": "ip-dst", "value": "93.184.216.34"},
            {"type": "vulnerability", "value": "CVE-2026-0001"},
        ]
        result = misp.create_event(
            info="Test event",
            attributes=attrs,
        )
        # Verify the body includes attributes
        call_args = mock_post.call_args
        body = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        assert "Event" in body
        assert "Attribute" in body["Event"]

    @patch("tip.core.integrations.misp_client.requests.get")
    def test_get_event(self, mock_get, misp):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"Event": {"id": "1234", "info": "Test"}},
            raise_for_status=lambda: None,
        )
        result = misp.get_event("1234")
        assert result["Event"]["id"] == "1234"


class TestMISPAttributes:
    """Test attribute creation and search."""

    @patch("tip.core.integrations.misp_client.requests.post")
    def test_add_attribute(self, mock_post, misp):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: ADD_ATTRIBUTE_RESPONSE,
            raise_for_status=lambda: None,
        )
        result = misp.add_attribute(
            event_id="1234",
            attr_type="ip-dst",
            value="93.184.216.34",
            comment="Asset IP",
        )
        assert "Attribute" in result

    @patch("tip.core.integrations.misp_client.requests.post")
    def test_search_attributes(self, mock_post, misp):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: SEARCH_ATTRIBUTES_RESPONSE,
            raise_for_status=lambda: None,
        )
        attrs = misp.search_attributes(value="93.184.216.34", type_attribute="ip-dst")
        assert len(attrs) == 2
        assert attrs[0]["value"] == "10.0.1.10"


class TestMISPHeaders:
    """Test that the client sends correct headers."""

    def test_headers_include_auth(self, misp):
        headers = misp._headers
        assert headers["Authorization"] == "test-misp-key"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"
