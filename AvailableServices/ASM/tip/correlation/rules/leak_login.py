"""
Correlation Rule: Data Leak with Active Login.

Fires when a data-leak contains passwords for a domain that matches
an active asset hosting a web service.
"""
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy.orm import Session

from tip.core.logger import get_logger
from tip.core.models import Alert, Asset, DataLeak, Organization

logger = get_logger(__name__)

_WEB_TECHS = {"wordpress", "drupal", "joomla", "php", "asp.net", "nginx", "apache", "iis"}


class LeakLoginRule:
    name = "leak_active_login"

    def __init__(self, db: Session):
        self.db = db

    def evaluate(self, org: Organization) -> List[Alert]:
        alerts: List[Alert] = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        # Recent leaks for this org that contain passwords
        leaks = (
            self.db.query(DataLeak)
            .filter(
                DataLeak.organization_id == org.id,
                DataLeak.contains_passwords.is_(True),
                DataLeak.discovered_date >= cutoff,
            )
            .all()
        )

        for leak in leaks:
            affected_domains = set(leak.affected_domains or [])
            if not affected_domains:
                continue

            # active web assets for this org
            web_assets = (
                self.db.query(Asset)
                .filter(
                    Asset.organization_id == org.id,
                    Asset.is_active.is_(True),
                )
                .all()
            )

            for asset in web_assets:
                # does the asset hostname appear in the leak's domains?
                if asset.hostname not in affected_domains:
                    continue

                # does the asset look like a web / login target?
                techs = {(t or "").lower() for t in (asset.technologies or [])}
                has_login = bool(techs & _WEB_TECHS) or asset.port in (80, 443, 8080, 8443)
                if not has_login:
                    continue

                # deduplicate
                existing = (
                    self.db.query(Alert)
                    .filter(
                        Alert.asset_id == asset.id,
                        Alert.leak_id == leak.id,
                        Alert.alert_type == "correlation_leak_login",
                    )
                    .first()
                )
                if existing:
                    continue

                alert = Alert(
                    source_module="correlation",
                    alert_type="correlation_leak_login",
                    severity="HIGH",
                    priority=1,
                    title=(
                        f"Credential leak affects active service "
                        f"on {asset.hostname}"
                    ),
                    description=(
                        f"Credentials from leak '{leak.leak_source}' "
                        f"({leak.record_count} records) may be valid for "
                        f"the service at {asset.hostname}:{asset.port}. "
                        f"Consider forcing password resets."
                    ),
                    raw_data={
                        "asset_hostname": asset.hostname,
                        "leak_source": leak.leak_source,
                        "record_count": leak.record_count,
                        "correlation_rule": self.name,
                    },
                    asset_id=asset.id,
                    leak_id=leak.id,
                )
                self.db.add(alert)
                alerts.append(alert)

        self.db.commit()
        return alerts
