"""
Unit tests for the IDS Alert Service.
"""
import pytest
from unittest.mock import MagicMock

from tip.core.models import Alert, Asset, WazuhEvent
from tip.modules.ids.alert_service import IDSAlertService
from tip.tests.fixtures.wazuh_responses import ALERTS_RESPONSE


class TestIDSIngestion:
    """Test Wazuh event ingestion."""

    def test_ingest_alerts(self, db_session):
        svc = IDSAlertService(db_session, wazuh_client=MagicMock())
        raw = ALERTS_RESPONSE["data"]["affected_items"]
        events = svc.ingest_alerts(raw)

        # All 4 raw alerts have level >= 7 (8, 10, 12, 15)
        assert len(events) == 4

        # Verify fields
        ev = events[0]
        assert ev.wazuh_id == "wazuh-alert-001"
        assert ev.rule_id == 5710
        assert ev.rule_level == 10
        assert ev.agent_id == "001"

    def test_ingest_deduplicates(self, db_session):
        svc = IDSAlertService(db_session, wazuh_client=MagicMock())
        raw = ALERTS_RESPONSE["data"]["affected_items"]

        # First ingestion
        events1 = svc.ingest_alerts(raw)
        assert len(events1) == 4

        # Second ingestion
        events2 = svc.ingest_alerts(raw)
        assert len(events2) == 0  # all deduplicated

    def test_ingest_filters_low_level(self, db_session):
        svc = IDSAlertService(db_session, wazuh_client=MagicMock())
        low_alerts = [
            {
                "id": "low-001",
                "timestamp": "2026-02-24T10:00:00Z",
                "rule": {"id": 1000, "level": 3, "description": "Low severity"},
                "agent": {"id": "001"},
            },
            {
                "id": "low-002",
                "timestamp": "2026-02-24T10:05:00Z",
                "rule": {"id": 1001, "level": 5, "description": "Medium-low"},
                "agent": {"id": "001"},
            },
        ]
        events = svc.ingest_alerts(low_alerts)
        assert len(events) == 0  # both below MIN_LEVEL=7

    def test_fetch_and_ingest(self, db_session):
        mock_wazuh = MagicMock()
        mock_wazuh.get_alerts.return_value = ALERTS_RESPONSE["data"]["affected_items"]

        svc = IDSAlertService(db_session, wazuh_client=mock_wazuh)
        events = svc.fetch_and_ingest(limit=100)

        assert len(events) == 4
        mock_wazuh.get_alerts.assert_called_once_with(level_min=7, limit=100)


class TestIDSAlertGeneration:
    """Test TIP Alert creation from Wazuh events."""

    def test_generate_alerts_from_events(self, db_session, sample_org):
        # Create asset linked to agent 001
        asset = Asset(
            organization_id=sample_org.id, asset_type="service",
            hostname="ubuntu-web", wazuh_agent_id="001", is_active=True,
        )
        db_session.add(asset)
        db_session.flush()

        svc = IDSAlertService(db_session, wazuh_client=MagicMock())
        raw = ALERTS_RESPONSE["data"]["affected_items"]
        events = svc.ingest_alerts(raw)
        alerts = svc.generate_alerts_from_events(events)

        # Should have 4 alerts (one per event)
        assert len(alerts) == 4

        # Events from agent 001 should be linked to the asset
        agent001_alerts = [a for a in alerts if a.asset_id == asset.id]
        assert len(agent001_alerts) >= 2  # alert-001 and alert-002

    def test_severity_mapping(self, db_session):
        svc = IDSAlertService(db_session, wazuh_client=MagicMock())
        assert svc._level_to_severity(15) == "CRITICAL"
        assert svc._level_to_severity(12) == "CRITICAL"
        assert svc._level_to_severity(10) == "HIGH"
        assert svc._level_to_severity(7) == "MEDIUM"
        assert svc._level_to_severity(4) == "LOW"
        assert svc._level_to_severity(2) == "INFO"

    def test_alert_without_asset_link(self, db_session):
        """Events from unknown agents should still create alerts."""
        svc = IDSAlertService(db_session, wazuh_client=MagicMock())
        ev = WazuhEvent(
            wazuh_id="orphan-001", rule_id=99, rule_level=12,
            rule_description="Unknown agent event",
            agent_id="999",  # no matching asset
        )
        db_session.add(ev)
        db_session.flush()

        alerts = svc.generate_alerts_from_events([ev])
        assert len(alerts) == 1
        assert alerts[0].asset_id is None
