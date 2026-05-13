"""
Data-Leak Collector.

Pulls leak intelligence from the Dummy Leak API (or any compatible
feed) and creates ``DataLeak`` + ``Alert`` records in the TIP database.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from tip.core.config import settings
from tip.core.logger import get_logger
from tip.core.models import Alert, DataLeak, Organization

logger = get_logger(__name__)


class LeakCollector:
    """Collect and process data-leak intelligence."""

    def __init__(self, db: Session, api_url: Optional[str] = None):
        self.db = db
        self.api_url = (api_url or settings.LEAK_API_URL).rstrip("/")

    # ── public API ───────────────────────────────────────────────

    def fetch_leaks_for_org(self, org: Organization) -> List[Dict]:
        """
        Query the leak feed for any entries matching the
        organization's domains (primary + asset hostnames).
        """
        domains = [org.primary_domain]
        for asset in org.assets:
            if asset.hostname and asset.hostname not in domains:
                domains.append(asset.hostname)

        try:
            resp = requests.post(
                f"{self.api_url}/api/v1/leaks/search",
                json={"domains": domains},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json().get("leaks", [])
        except Exception as exc:
            logger.error("Error fetching leaks for %s: %s", org.name, exc)
            return []

    def process_leaks(self, org: Organization) -> List[Alert]:
        """
        Fetch leaks → deduplicate → persist DataLeak records →
        create Alert records.
        """
        raw_leaks = self.fetch_leaks_for_org(org)
        alerts: List[Alert] = []

        for raw in raw_leaks:
            try:
                discovered = raw.get("discovered_date", "")
                leak_dt = (
                    datetime.fromisoformat(discovered.replace("Z", "+00:00"))
                    if discovered
                    else datetime.now(timezone.utc)
                )

                # deduplicate by (org, source, date)
                existing = (
                    self.db.query(DataLeak)
                    .filter(
                        DataLeak.organization_id == org.id,
                        DataLeak.leak_source == raw.get("source"),
                        DataLeak.leak_date == leak_dt,
                    )
                    .first()
                )
                if existing:
                    continue

                leak = DataLeak(
                    organization_id=org.id,
                    leak_source=raw.get("source"),
                    leak_type=raw.get("type"),
                    leak_date=leak_dt,
                    affected_emails=raw.get("affected_emails", []),
                    affected_domains=raw.get("affected_domains", []),
                    record_count=raw.get("record_count", 0),
                    sample_data=raw.get("sample", []),
                    severity=raw.get("severity", "MEDIUM"),
                    contains_passwords=raw.get("contains_passwords", False),
                    contains_pii=raw.get("contains_pii", False),
                    status="new",
                )
                self.db.add(leak)
                self.db.flush()

                alert = Alert(
                    source_module="data_leak",
                    alert_type="data_breach",
                    severity=leak.severity or "MEDIUM",
                    priority=1 if leak.severity == "CRITICAL" else 2,
                    title=f"Data leak detected for {org.primary_domain}",
                    description=(
                        f"Leak from '{leak.leak_source}' discovered with "
                        f"{leak.record_count} records. "
                        f"{'Contains passwords. ' if leak.contains_passwords else ''}"
                        f"{'Contains PII. ' if leak.contains_pii else ''}"
                        f"Emails: {', '.join((leak.affected_emails or [])[:5])}"
                    ),
                    raw_data=raw,
                    leak_id=leak.id,
                )
                self.db.add(alert)
                alerts.append(alert)

                logger.warning(
                    "New leak for %s: %s – %d records",
                    org.primary_domain,
                    leak.leak_source,
                    leak.record_count,
                )
            except Exception as exc:
                logger.error("Error processing leak: %s", exc)

        self.db.commit()
        return alerts
