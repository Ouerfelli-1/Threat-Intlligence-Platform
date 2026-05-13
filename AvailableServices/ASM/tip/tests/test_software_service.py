"""
Unit tests for the Software Inventory Service.
"""
import pytest
from unittest.mock import MagicMock

from tip.core.models import Asset, Software
from tip.modules.asm.software_service import SoftwareService
from tip.tests.fixtures.wazuh_responses import PACKAGES_AGENT_001


class TestSoftwareSync:
    """Test syncing software from Wazuh Syscollector."""

    def test_sync_software_for_asset(self, db_session, sample_asset):
        mock_wazuh = MagicMock()
        mock_wazuh.get_agent_packages.return_value = (
            PACKAGES_AGENT_001["data"]["affected_items"]
        )

        svc = SoftwareService(db_session, wazuh_client=mock_wazuh)
        synced = svc.sync_software_for_asset(sample_asset)

        assert len(synced) == 6
        names = [s.name for s in synced]
        assert "apache2" in names
        assert "openssl" in names
        assert "mysql-server" in names

    def test_sync_skips_asset_without_agent(self, db_session, sample_org):
        asset = Asset(
            organization_id=sample_org.id,
            asset_type="subdomain",
            hostname="no-agent.example.com",
            wazuh_agent_id=None,
        )
        db_session.add(asset)
        db_session.flush()

        svc = SoftwareService(db_session, wazuh_client=MagicMock())
        synced = svc.sync_software_for_asset(asset)
        assert synced == []

    def test_sync_links_m2m(self, db_session, sample_asset):
        mock_wazuh = MagicMock()
        mock_wazuh.get_agent_packages.return_value = [
            {"name": "curl", "version": "7.81.0", "vendor": "Ubuntu", "architecture": "amd64"}
        ]

        svc = SoftwareService(db_session, wazuh_client=mock_wazuh)
        synced = svc.sync_software_for_asset(sample_asset)
        assert len(synced) == 1
        assert synced[0] in sample_asset.software

    def test_sync_deduplicates_software(self, db_session, sample_asset):
        mock_wazuh = MagicMock()
        pkgs = [
            {"name": "curl", "version": "7.81.0", "vendor": "Ubuntu"},
        ]
        mock_wazuh.get_agent_packages.return_value = pkgs

        svc = SoftwareService(db_session, wazuh_client=mock_wazuh)
        # First sync
        svc.sync_software_for_asset(sample_asset)
        # Second sync with same data
        svc.sync_software_for_asset(sample_asset)

        # Should only have one Software record
        all_sw = db_session.query(Software).filter(Software.name == "curl").all()
        assert len(all_sw) == 1

    def test_sync_all_assets_for_org(self, db_session, sample_org):
        a1 = Asset(
            organization_id=sample_org.id, asset_type="service",
            hostname="a1.example.com", wazuh_agent_id="001", is_active=True,
        )
        a2 = Asset(
            organization_id=sample_org.id, asset_type="service",
            hostname="a2.example.com", wazuh_agent_id="002", is_active=True,
        )
        db_session.add_all([a1, a2])
        db_session.flush()

        mock_wazuh = MagicMock()
        mock_wazuh.get_agent_packages.return_value = [
            {"name": "nginx", "version": "1.20.1", "vendor": "CentOS"},
        ]

        svc = SoftwareService(db_session, wazuh_client=mock_wazuh)
        total = svc.sync_all_assets_for_org(sample_org.id)
        assert total == 2  # 1 package per agent * 2 agents


class TestCPEGeneration:
    """Test CPE 2.3 string generation."""

    def test_basic_cpe(self):
        cpe = SoftwareService.generate_cpe("Apache", "httpd", "2.4.52")
        assert cpe == "cpe:2.3:a:apache:httpd:2.4.52:*:*:*:*:*:*:*"

    def test_cpe_with_spaces(self):
        cpe = SoftwareService.generate_cpe("Ubuntu Developers", "open ssl", "3.0.2")
        assert cpe == "cpe:2.3:a:ubuntu_developers:open_ssl:3.0.2:*:*:*:*:*:*:*"

    def test_cpe_missing_vendor(self):
        cpe = SoftwareService.generate_cpe(None, "nginx", "1.20.1")
        assert cpe == "cpe:2.3:a:*:nginx:1.20.1:*:*:*:*:*:*:*"

    def test_cpe_all_wildcards(self):
        cpe = SoftwareService.generate_cpe(None, None, None)
        assert cpe == "cpe:2.3:a:*:*:*:*:*:*:*:*:*:*"

    def test_cpe_lowercase(self):
        cpe = SoftwareService.generate_cpe("Microsoft", "IIS", "10.0")
        assert cpe == "cpe:2.3:a:microsoft:iis:10.0:*:*:*:*:*:*:*"
