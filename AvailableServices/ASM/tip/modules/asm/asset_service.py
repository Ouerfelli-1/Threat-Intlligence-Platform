"""
ASM Asset Ingestion Service.

Reads recon findings from the existing Findings API and upserts
them into the TIP ``assets`` table so that other modules
(vuln-intel, data-leak, correlation) can use them.
"""
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from tip.core.integrations.recon_client import ReconClient
from tip.core.logger import get_logger
from tip.core.models import Asset, Organization

logger = get_logger(__name__)


class AssetService:
    """Syncs assets from the recon platform into the TIP database."""

    def __init__(self, db: Session, recon_client: Optional[ReconClient] = None):
        self.db = db
        self.recon = recon_client or ReconClient()

    # ── public API ───────────────────────────────────────────────

    def sync_assets_from_recon(self, org: Organization) -> List[Asset]:
        """
        Pull subdomains, services, IPs from the Findings API for the
        scope linked to *org* and upsert them into the assets table.
        """
        if not org.recon_scope_id:
            logger.warning("Organization %s has no linked recon scope", org.name)
            return []

        scope_id = org.recon_scope_id
        synced: List[Asset] = []

        # 1 ─ subdomains
        try:
            sub_data = self.recon.get_scope_subdomains(scope_id)
            for item in sub_data.get("subdomains", []):
                hostname = item if isinstance(item, str) else item.get("value", "")
                if hostname:
                    asset = self._upsert_asset(
                        org=org,
                        asset_type="subdomain",
                        hostname=hostname,
                        source="recon_subdomain",
                    )
                    synced.append(asset)
        except Exception as exc:
            logger.error("Error syncing subdomains for %s: %s", org.name, exc)

        # 2 ─ ports / services
        try:
            port_data = self.recon.get_scope_ports(scope_id)
            for svc in port_data.get("ports", []):
                asset = self._upsert_asset(
                    org=org,
                    asset_type="service",
                    hostname=svc.get("hostname"),
                    ip_address=svc.get("ip") or svc.get("ip_address"),
                    port=svc.get("port"),
                    source="recon_portscan",
                    extra_data=svc,
                )
                synced.append(asset)
        except Exception as exc:
            logger.error("Error syncing ports for %s: %s", org.name, exc)

        # 3 ─ services (with technology fingerprints)
        try:
            svc_data = self.recon.get_scope_services(scope_id)
            for svc in svc_data.get("services", []):
                techs = []
                if svc.get("service"):
                    techs.append(svc["service"])
                if svc.get("product"):
                    techs.append(svc["product"])

                asset = self._upsert_asset(
                    org=org,
                    asset_type="service",
                    hostname=svc.get("hostname"),
                    ip_address=svc.get("ip") or svc.get("ip_address"),
                    port=svc.get("port"),
                    source="recon_service",
                    technologies=techs if techs else None,
                    extra_data=svc,
                )
                synced.append(asset)
        except Exception as exc:
            logger.error("Error syncing services for %s: %s", org.name, exc)

        self.db.commit()
        logger.info("Synced %d assets for %s", len(synced), org.name)
        return synced

    # ── helpers ──────────────────────────────────────────────────

    def _upsert_asset(
        self,
        org: Organization,
        asset_type: str,
        hostname: Optional[str] = None,
        ip_address: Optional[str] = None,
        port: Optional[int] = None,
        source: Optional[str] = None,
        technologies: Optional[List[str]] = None,
        extra_data: Optional[Dict] = None,
    ) -> Asset:
        """Insert or update an asset (dedup by org + hostname + ip + port)."""
        q = self.db.query(Asset).filter(
            Asset.organization_id == org.id,
            Asset.asset_type == asset_type,
        )
        if hostname:
            q = q.filter(Asset.hostname == hostname)
        if ip_address:
            q = q.filter(Asset.ip_address == ip_address)
        if port is not None:
            q = q.filter(Asset.port == port)

        existing = q.first()

        if existing:
            from datetime import datetime, timezone
            existing.last_seen = datetime.now(timezone.utc)
            existing.is_active = True
            if technologies:
                existing.technologies = technologies
            if extra_data:
                existing.extra_data = extra_data
            return existing

        asset = Asset(
            organization_id=org.id,
            asset_type=asset_type,
            hostname=hostname,
            ip_address=ip_address,
            port=port,
            discovery_source=source,
            technologies=technologies,
            extra_data=extra_data,
            is_active=True,
        )
        self.db.add(asset)
        self.db.flush()
        return asset

    def get_assets_for_org(self, org_id: int, active_only: bool = True) -> List[Asset]:
        q = self.db.query(Asset).filter(Asset.organization_id == org_id)
        if active_only:
            q = q.filter(Asset.is_active.is_(True))
        return q.all()

    def get_asset_by_id(self, asset_id: int) -> Optional[Asset]:
        return self.db.get(Asset, asset_id)
