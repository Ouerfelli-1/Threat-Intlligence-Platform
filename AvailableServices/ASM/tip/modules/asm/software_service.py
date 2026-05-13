"""
Software Inventory Service.

Syncs installed software from Wazuh Syscollector into the TIP
database and links it to assets via the asset_software M2M table.
"""
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from tip.core.integrations.wazuh_client import WazuhClient
from tip.core.logger import get_logger
from tip.core.models import Asset, Software

logger = get_logger(__name__)


class SoftwareService:
    """Manages software inventory and Wazuh synchronization."""

    def __init__(self, db: Session, wazuh_client: Optional[WazuhClient] = None):
        self.db = db
        self.wazuh = wazuh_client or WazuhClient()

    # ── public API ───────────────────────────────────────────────

    def sync_software_for_asset(self, asset: Asset) -> List[Software]:
        """
        Pull installed packages from Wazuh for a single asset
        and link them in the database.

        Requires ``asset.wazuh_agent_id`` to be set.
        """
        if not asset.wazuh_agent_id:
            logger.debug("Asset %s (id=%d) has no wazuh_agent_id – skipping", asset.hostname, asset.id)
            return []

        packages = self.wazuh.get_agent_packages(asset.wazuh_agent_id)
        synced: List[Software] = []

        for pkg in packages:
            software = self._upsert_software(pkg)
            # link M2M if not already linked
            if software not in asset.software:
                asset.software.append(software)
            synced.append(software)

        self.db.commit()
        logger.info(
            "Synced %d packages for asset %s (agent %s)",
            len(synced),
            asset.hostname,
            asset.wazuh_agent_id,
        )
        return synced

    def sync_all_assets_for_org(self, org_id: int) -> int:
        """Sync software for every asset in an organization that has a Wazuh agent."""
        assets = (
            self.db.query(Asset)
            .filter(
                Asset.organization_id == org_id,
                Asset.wazuh_agent_id.isnot(None),
                Asset.is_active.is_(True),
            )
            .all()
        )
        total = 0
        for asset in assets:
            sw = self.sync_software_for_asset(asset)
            total += len(sw)
        return total

    # ── CPE generation ───────────────────────────────────────────

    @staticmethod
    def generate_cpe(
        vendor: Optional[str] = None,
        product: Optional[str] = None,
        version: Optional[str] = None,
    ) -> str:
        """
        Build a CPE 2.3 string from package metadata.

        See https://nvd.nist.gov/products/cpe for format reference.
        """
        v = (vendor or "*").lower().strip().replace(" ", "_")
        p = (product or "*").lower().strip().replace(" ", "_")
        ver = (version or "*").strip()
        return f"cpe:2.3:a:{v}:{p}:{ver}:*:*:*:*:*:*:*"

    # ── helpers ──────────────────────────────────────────────────

    def _upsert_software(self, pkg: Dict) -> Software:
        """Insert or look-up a Software record (dedup by name+version)."""
        name = pkg.get("name", "unknown")
        version = pkg.get("version")

        existing = self.db.query(Software).filter(
            Software.name == name,
            Software.version == version,
        ).first()

        if existing:
            return existing

        vendor = pkg.get("vendor")
        cpe = self.generate_cpe(vendor=vendor, product=name, version=version)

        sw = Software(
            name=name,
            vendor=vendor,
            version=version,
            cpe=cpe,
            architecture=pkg.get("architecture"),
        )
        self.db.add(sw)
        self.db.flush()
        return sw
