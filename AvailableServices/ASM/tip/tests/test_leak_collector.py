"""
Unit tests for the Data-Leak Collector.
"""
import pytest
from unittest.mock import patch, MagicMock

from tip.core.models import Alert, DataLeak
from tip.modules.data_leak.collectors.leak_collector import LeakCollector
from tip.tests.fixtures.leak_responses import (
    LEAK_SEARCH_RESPONSE_EXAMPLE_COM,
    LEAK_SEARCH_NO_RESULTS,
)


class TestLeakFetch:
    """Test fetching leaks from the API."""

    @patch("tip.modules.data_leak.collectors.leak_collector.requests.post")
    def test_fetch_leaks_for_org(self, mock_post, db_session, sample_org):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: LEAK_SEARCH_RESPONSE_EXAMPLE_COM,
            raise_for_status=lambda: None,
        )
        collector = LeakCollector(db_session, api_url="http://mock-leak:8081")
        leaks = collector.fetch_leaks_for_org(sample_org)
        assert len(leaks) == 1
        assert leaks[0]["source"] == "DarkMarket Forums"

    @patch("tip.modules.data_leak.collectors.leak_collector.requests.post")
    def test_fetch_leaks_no_results(self, mock_post, db_session, sample_org):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: LEAK_SEARCH_NO_RESULTS,
            raise_for_status=lambda: None,
        )
        collector = LeakCollector(db_session, api_url="http://mock-leak:8081")
        leaks = collector.fetch_leaks_for_org(sample_org)
        assert leaks == []

    @patch("tip.modules.data_leak.collectors.leak_collector.requests.post")
    def test_fetch_leaks_api_error(self, mock_post, db_session, sample_org):
        mock_post.side_effect = Exception("Connection refused")
        collector = LeakCollector(db_session, api_url="http://mock-leak:8081")
        leaks = collector.fetch_leaks_for_org(sample_org)
        assert leaks == []


class TestLeakProcessing:
    """Test leak processing pipeline (dedup + persist + alert)."""

    @patch("tip.modules.data_leak.collectors.leak_collector.requests.post")
    def test_process_leaks_creates_records(self, mock_post, db_session, sample_org):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: LEAK_SEARCH_RESPONSE_EXAMPLE_COM,
            raise_for_status=lambda: None,
        )
        collector = LeakCollector(db_session, api_url="http://mock-leak:8081")
        alerts = collector.process_leaks(sample_org)

        assert len(alerts) == 1
        assert alerts[0].source_module == "data_leak"
        assert alerts[0].alert_type == "data_breach"

        # Verify DataLeak record created
        leaks = db_session.query(DataLeak).filter(
            DataLeak.organization_id == sample_org.id
        ).all()
        assert len(leaks) == 1
        assert leaks[0].leak_source == "DarkMarket Forums"
        assert leaks[0].contains_passwords is True

    @patch("tip.modules.data_leak.collectors.leak_collector.requests.post")
    def test_process_leaks_deduplicates(self, mock_post, db_session, sample_org):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: LEAK_SEARCH_RESPONSE_EXAMPLE_COM,
            raise_for_status=lambda: None,
        )
        collector = LeakCollector(db_session, api_url="http://mock-leak:8081")

        # First run
        alerts1 = collector.process_leaks(sample_org)
        assert len(alerts1) == 1

        # Second run with same data
        alerts2 = collector.process_leaks(sample_org)
        assert len(alerts2) == 0  # deduplicated

    @patch("tip.modules.data_leak.collectors.leak_collector.requests.post")
    def test_process_leaks_alert_details(self, mock_post, db_session, sample_org):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: LEAK_SEARCH_RESPONSE_EXAMPLE_COM,
            raise_for_status=lambda: None,
        )
        collector = LeakCollector(db_session, api_url="http://mock-leak:8081")
        alerts = collector.process_leaks(sample_org)

        alert = alerts[0]
        assert "example.com" in alert.title
        assert "1500 records" in alert.description
        assert "Contains passwords" in alert.description
