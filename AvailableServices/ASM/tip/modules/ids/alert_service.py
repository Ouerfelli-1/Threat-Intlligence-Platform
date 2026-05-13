"""
IDS Alert Service.

Ingests security alerts from Wazuh, persists them as ``WazuhEvent``
records, and generates TIP ``Alert`` records for high-severity events.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from tip.core.integrations.wazuh_client import WazuhClient
from tip.core.logger import get_logger
from tip.core.models import Alert, Asset, WazuhEvent

logger = get_logger(__name__)


class IDSAlertService:
    """Ingest and correlate Wazuh IDS alerts."""

    # Minimum Wazuh rule level to ingest (7 = high)
    MIN_LEVEL = 7

    def __init__(self, db: Session, wazuh_client: Optional[WazuhClient] = None):
        self.db = db
        self.wazuh = wazuh_client or WazuhClient()

    # ── public API ───────────────────────────────────────────────

    def fetch_and_ingest(self, limit: int = 200) -> List[WazuhEvent]:
        """
        Fetch recent high-level alerts from Wazuh and store them.
        """
        raw_alerts = self.wazuh.get_alerts(level_min=self.MIN_LEVEL, limit=limit)
        return self.ingest_alerts(raw_alerts)

    def ingest_alerts(self, raw_alerts: List[Dict]) -> List[WazuhEvent]:
        """
        Parse and store a list of raw Wazuh alert dicts.
        Deduplicates by ``wazuh_id``.
        """
        events: List[WazuhEvent] = []
        for raw in raw_alerts:
            wazuh_id = raw.get("id")
            rule = raw.get("rule", {})
            rule_level = rule.get("level", 0)

            if rule_level < self.MIN_LEVEL:
                continue

            # deduplicate
            if wazuh_id:
                exists = (
                    self.db.query(WazuhEvent)
                    .filter(WazuhEvent.wazuh_id == wazuh_id)
                    .first()
                )
                if exists:
                    continue

            agent = raw.get("agent", {})
            event = WazuhEvent(
                wazuh_id=wazuh_id,
                rule_id=rule.get("id"),
                rule_level=rule_level,
                rule_description=rule.get("description"),
                agent_id=agent.get("id"),
                agent_name=agent.get("name"),
                source_ip=raw.get("data", {}).get("srcip")
                or raw.get("srcip"),
                full_log=raw.get("full_log"),
                decoded_data=raw.get("data"),
                timestamp=(
                    datetime.fromisoformat(raw["timestamp"].replace("Z", "+00:00"))
                    if raw.get("timestamp")
                    else datetime.now(timezone.utc)
                ),
            )
            self.db.add(event)
            events.append(event)

        self.db.commit()
        logger.info("Ingested %d Wazuh events", len(events))
        return events

    # ── alert generation ─────────────────────────────────────────

    def generate_alerts_from_events(self, events: List[WazuhEvent]) -> List[Alert]:
        """
        Create TIP ``Alert`` records from high-severity Wazuh events,
        linking them to assets where possible.
        """
        alerts: List[Alert] = []

        for ev in events:
            # try to link to an asset by agent_id
            asset = None
            if ev.agent_id:
                asset = (
                    self.db.query(Asset)
                    .filter(Asset.wazuh_agent_id == ev.agent_id)
                    .first()
                )

            severity = self._level_to_severity(ev.rule_level or 0)

            alert = Alert(
                source_module="ids",
                alert_type="wazuh_alert",
                severity=severity,
                priority=2 if severity in ("CRITICAL", "HIGH") else 3,
                title=f"IDS: {ev.rule_description or 'Wazuh alert'}",
                description=(
                    f"Wazuh rule {ev.rule_id} (level {ev.rule_level}): "
                    f"{ev.rule_description}. "
                    f"Agent: {ev.agent_name or ev.agent_id or 'unknown'}. "
                    f"Source IP: {ev.source_ip or 'N/A'}"
                ),
                raw_data={
                    "wazuh_id": ev.wazuh_id,
                    "rule_id": ev.rule_id,
                    "rule_level": ev.rule_level,
                    "agent_id": ev.agent_id,
                    "source_ip": ev.source_ip,
                },
                asset_id=asset.id if asset else None,
            )
            self.db.add(alert)
            alerts.append(alert)

        self.db.commit()
        return alerts

    # ── helpers ──────────────────────────────────────────────────

    @staticmethod
    def _level_to_severity(level: int) -> str:
        if level >= 12:
            return "CRITICAL"
        if level >= 10:
            return "HIGH"
        if level >= 7:
            return "MEDIUM"
        if level >= 4:
            return "LOW"
        return "INFO"
