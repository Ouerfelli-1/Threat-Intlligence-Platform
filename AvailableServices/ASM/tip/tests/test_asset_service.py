"""
Unit tests for the ASM Asset Service.
"""
import pytest
from unittest.mock import MagicMock, patch

from tip.core.models import Asset, Organization
from tip.modules.asm.asset_service import AssetService
from tip.tests.fixtures.recon_responses import (
    SCOPE_SUBDOMAINS_RESPONSE,
    SCOPE_SERVICES_RESPONSE,
)


class TestAssetSync:
    """Test syncing assets from the recon platform."""

    def test_sync_assets_from_recon(self, db_session, sample_org):
        mock_recon = MagicMock()
        mock_recon.get_scope_subdomains.return_value = SCOPE_SUBDOMAINS_RESPONSE
        mock_recon.get_scope_ports.return_value = {"ports": [
            {"hostname": "www.example.com", "ip": "93.184.216.34", "port": 443},
            {"hostname": "www.example.com", "ip": "93.184.216.34", "port": 80},
        ]}
        mock_recon.get_scope_services.return_value = SCOPE_SERVICES_RESPONSE

        svc = AssetService(db_session, recon_client=mock_recon)
        synced = svc.sync_assets_from_recon(sample_org)

        # 4 subdomains + 2 ports + 3 services
        assert len(synced) >= 4
        mock_recon.get_scope_subdomains.assert_called_once_with("scope-uuid-001")

    def test_sync_no_scope_id(self, db_session, sample_org):
        sample_org.recon_scope_id = None
        svc = AssetService(db_session, recon_client=MagicMock())
        synced = svc.sync_assets_from_recon(sample_org)
        assert synced == []

    def test_sync_creates_subdomain_assets(self, db_session, sample_org):
        mock_recon = MagicMock()
        mock_recon.get_scope_subdomains.return_value = {
            "subdomains": [
                {"value": "blog.example.com"},
                {"value": "shop.example.com"},
            ]
        }
        mock_recon.get_scope_ports.return_value = {"ports": []}
        mock_recon.get_scope_services.return_value = {"services": []}

        svc = AssetService(db_session, recon_client=mock_recon)
        synced = svc.sync_assets_from_recon(sample_org)
        assert len(synced) == 2
        hostnames = [a.hostname for a in synced]
        assert "blog.example.com" in hostnames
        assert "shop.example.com" in hostnames


class TestAssetDedup:
    """Test deduplication logic in _upsert_asset."""

    def test_upsert_creates_new_asset(self, db_session, sample_org):
        svc = AssetService(db_session, recon_client=MagicMock())
        asset = svc._upsert_asset(
            org=sample_org,
            asset_type="subdomain",
            hostname="new.example.com",
            source="test",
        )
        db_session.flush()
        assert asset.id is not None
        assert asset.hostname == "new.example.com"

    def test_upsert_updates_existing(self, db_session, sample_org):
        svc = AssetService(db_session, recon_client=MagicMock())
        # Create first
        a1 = svc._upsert_asset(
            org=sample_org,
            asset_type="service",
            hostname="web.example.com",
            ip_address="10.0.0.1",
            port=443,
        )
        db_session.flush()
        first_id = a1.id

        # Upsert same
        a2 = svc._upsert_asset(
            org=sample_org,
            asset_type="service",
            hostname="web.example.com",
            ip_address="10.0.0.1",
            port=443,
            technologies=["nginx"],
        )
        assert a2.id == first_id
        assert a2.technologies == ["nginx"]


class TestAssetQueries:
    """Test asset query methods."""

    def test_get_assets_for_org(self, db_session, sample_org, sample_asset):
        svc = AssetService(db_session, recon_client=MagicMock())
        assets = svc.get_assets_for_org(sample_org.id)
        assert len(assets) == 1
        assert assets[0].hostname == "www.example.com"

    def test_get_assets_active_only(self, db_session, sample_org):
        active = Asset(
            organization_id=sample_org.id,
            asset_type="subdomain",
            hostname="active.example.com",
            is_active=True,
        )
        inactive = Asset(
            organization_id=sample_org.id,
            asset_type="subdomain",
            hostname="old.example.com",
            is_active=False,
        )
        db_session.add_all([active, inactive])
        db_session.flush()

        svc = AssetService(db_session, recon_client=MagicMock())
        result = svc.get_assets_for_org(sample_org.id, active_only=True)
        hostnames = [a.hostname for a in result]
        assert "active.example.com" in hostnames
        assert "old.example.com" not in hostnames

    def test_get_asset_by_id(self, db_session, sample_asset):
        svc = AssetService(db_session, recon_client=MagicMock())
        asset = svc.get_asset_by_id(sample_asset.id)
        assert asset is not None
        assert asset.hostname == "www.example.com"
