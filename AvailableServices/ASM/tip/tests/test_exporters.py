"""
Unit tests for MISP and OpenCTI Exporters.
"""
import pytest
from unittest.mock import MagicMock, patch

from tip.core.models import Alert, Asset
from tip.correlation.exporters.misp_exporter import MISPExporter
from tip.correlation.exporters.opencti_exporter import OpenCTIExporter
from tip.tests.fixtures.misp_responses import CREATE_EVENT_RESPONSE
from tip.tests.fixtures.opencti_responses import (
    CREATE_INDICATOR_RESPONSE,
    CREATE_REPORT_RESPONSE,
    CREATE_VULNERABILITY_RESPONSE,
)


class TestMISPExporter:
    """Test MISP event export."""

    def _make_alert(self, db_session, sample_org, sample_asset):
        alert = Alert(
            source_module="vuln_intel",
            alert_type="cve_match",
            severity="CRITICAL",
            title="CVE-2026-0001 affects web server",
            description="Critical vulnerability on web.example.com",
            raw_data={"cve_id": "CVE-2026-0001"},
            asset_id=sample_asset.id,
        )
        db_session.add(alert)
        db_session.flush()
        return alert

    def test_export_alert_success(self, db_session, sample_org, sample_asset):
        alert = self._make_alert(db_session, sample_org, sample_asset)

        mock_misp = MagicMock()
        # Simulate successful event creation
        mock_misp.create_event.return_value = {
            "Event": {"id": "1234"},
            "uuid": "uuid-1234",
            "id": "1234",
        }

        exporter = MISPExporter(db_session, misp_client=mock_misp)
        event_id = exporter.export_alert(alert)

        assert event_id is not None
        assert alert.misp_event_id is not None
        mock_misp.create_event.assert_called_once()

    def test_export_skips_already_exported(self, db_session, sample_org, sample_asset):
        alert = self._make_alert(db_session, sample_org, sample_asset)
        alert.misp_event_id = "already-exported-123"
        db_session.flush()

        mock_misp = MagicMock()
        exporter = MISPExporter(db_session, misp_client=mock_misp)
        result = exporter.export_alert(alert)

        assert result == "already-exported-123"
        mock_misp.create_event.assert_not_called()

    def test_export_includes_attributes(self, db_session, sample_org, sample_asset):
        alert = self._make_alert(db_session, sample_org, sample_asset)

        mock_misp = MagicMock()
        mock_misp.create_event.return_value = {"id": "5678"}

        exporter = MISPExporter(db_session, misp_client=mock_misp)
        exporter.export_alert(alert)

        call_kwargs = mock_misp.create_event.call_args
        attrs = call_kwargs[1].get("attributes") or call_kwargs.kwargs.get("attributes")
        assert attrs is not None
        attr_types = [a["type"] for a in attrs]
        assert "ip-dst" in attr_types  # from asset
        assert "vulnerability" in attr_types  # from CVE

    def test_severity_to_threat_level(self):
        assert MISPExporter._severity_to_threat_level("CRITICAL") == 1
        assert MISPExporter._severity_to_threat_level("HIGH") == 1
        assert MISPExporter._severity_to_threat_level("MEDIUM") == 2
        assert MISPExporter._severity_to_threat_level("LOW") == 3
        assert MISPExporter._severity_to_threat_level("INFO") == 4

    def test_export_handles_error(self, db_session, sample_org, sample_asset):
        alert = self._make_alert(db_session, sample_org, sample_asset)

        mock_misp = MagicMock()
        mock_misp.create_event.side_effect = Exception("Connection failed")

        exporter = MISPExporter(db_session, misp_client=mock_misp)
        result = exporter.export_alert(alert)
        assert result is None
        assert alert.misp_event_id is None


class TestOpenCTIExporter:
    """Test OpenCTI report export."""

    def _make_alert(self, db_session, sample_org, sample_asset):
        alert = Alert(
            source_module="correlation",
            alert_type="correlation_critical_exposed",
            severity="CRITICAL",
            title="CRITICAL: Exposed asset with critical CVE",
            description="Asset web.example.com has critical vulnerabilities",
            raw_data={"cves": ["CVE-2026-0001"], "asset_ip": "93.184.216.34"},
            asset_id=sample_asset.id,
        )
        db_session.add(alert)
        db_session.flush()
        return alert

    def test_export_alert_success(self, db_session, sample_org, sample_asset):
        alert = self._make_alert(db_session, sample_org, sample_asset)

        mock_opencti = MagicMock()
        mock_opencti.create_indicator.return_value = {"id": "indicator--uuid-001"}
        mock_opencti.create_vulnerability.return_value = {"id": "vulnerability--uuid-001"}
        mock_opencti.create_report.return_value = {"id": "report--uuid-001"}

        exporter = OpenCTIExporter(db_session, opencti_client=mock_opencti)
        report_id = exporter.export_alert(alert)

        assert report_id == "report--uuid-001"
        assert alert.opencti_report_id == "report--uuid-001"
        mock_opencti.create_report.assert_called_once()

    def test_export_skips_already_exported(self, db_session, sample_org, sample_asset):
        alert = self._make_alert(db_session, sample_org, sample_asset)
        alert.opencti_report_id = "already-exported"
        db_session.flush()

        mock_opencti = MagicMock()
        exporter = OpenCTIExporter(db_session, opencti_client=mock_opencti)
        result = exporter.export_alert(alert)

        assert result == "already-exported"
        mock_opencti.create_report.assert_not_called()

    def test_export_creates_stix_objects(self, db_session, sample_org, sample_asset):
        alert = self._make_alert(db_session, sample_org, sample_asset)

        mock_opencti = MagicMock()
        mock_opencti.create_indicator.return_value = {"id": "ind-1"}
        mock_opencti.create_vulnerability.return_value = {"id": "vuln-1"}
        mock_opencti.create_report.return_value = {"id": "report-1"}

        exporter = OpenCTIExporter(db_session, opencti_client=mock_opencti)
        exporter.export_alert(alert)

        # Should create: IP indicator + domain indicator + vulnerability
        assert mock_opencti.create_indicator.call_count == 2
        assert mock_opencti.create_vulnerability.call_count == 1

    def test_export_handles_error(self, db_session, sample_org, sample_asset):
        alert = self._make_alert(db_session, sample_org, sample_asset)

        mock_opencti = MagicMock()
        mock_opencti.create_indicator.side_effect = Exception("Connection failed")
        mock_opencti.create_report.side_effect = Exception("Connection failed")

        exporter = OpenCTIExporter(db_session, opencti_client=mock_opencti)
        result = exporter.export_alert(alert)
        assert result is None
