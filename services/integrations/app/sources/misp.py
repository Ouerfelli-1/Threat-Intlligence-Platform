"""
MISP threat sharing integration.
Pulls events + attributes and supports pushing high-confidence IOCs back.
"""
import logging
import uuid
from datetime import date, datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tip_http import build_resilient_client
from tip_schemas.indicators import IndicatorType, normalize_indicator
from tip_source_health import SourceHealthRepository

from app.models import MISPEvent, MISPIoc, MISPPush

log = logging.getLogger(__name__)
SOURCE_NAME = "misp"

# Map MISP attribute types to our indicator types
_MISP_TYPE_MAP = {
    "ip-src": IndicatorType.IP,
    "ip-dst": IndicatorType.IP,
    "domain": IndicatorType.DOMAIN,
    "hostname": IndicatorType.DOMAIN,
    "url": IndicatorType.URL,
    "md5": IndicatorType.MD5,
    "sha1": IndicatorType.SHA1,
    "sha256": IndicatorType.SHA256,
}


async def sync_misp(
    session: AsyncSession,
    health: SourceHealthRepository,
    base_url: str,
    api_key: str,
    since_days: int = 7,
) -> dict:
    if not base_url or not api_key:
        log.info("misp skipped: no credentials configured")
        return {"events": 0, "iocs": 0}

    if await health.is_open(SOURCE_NAME):
        return {"events": 0, "iocs": 0}

    headers = {"Authorization": api_key, "Accept": "application/json"}

    try:
        async with build_resilient_client(base_url=base_url, headers=headers) as client:
            events_count, iocs_count = await _pull_events(session, client, since_days)

        await session.commit()
        await health.mark_success(SOURCE_NAME)
        log.info("misp synced events=%d iocs=%d", events_count, iocs_count)
        return {"events": events_count, "iocs": iocs_count}

    except Exception as exc:
        log.error("misp sync error=%s", exc)
        await health.mark_failure(SOURCE_NAME, str(exc))
        return {"events": 0, "iocs": 0}


async def _pull_events(session: AsyncSession, client: httpx.AsyncClient, since_days: int) -> tuple[int, int]:
    resp = await client.post(
        "/events/index",
        json={"last": f"{since_days}d", "limit": 200},
        timeout=30,
    )
    resp.raise_for_status()
    events_data = resp.json() if isinstance(resp.json(), list) else []

    events_count = 0
    iocs_count = 0

    for event in events_data:
        event_id = str(event.get("id", ""))
        if not event_id:
            continue

        date_val = None
        if event.get("date"):
            try:
                date_val = date.fromisoformat(event["date"])
            except Exception:
                pass

        stmt = insert(MISPEvent.__table__).values(
            event_id=event_id,
            info=event.get("info", "")[:1024],
            threat_level_id=event.get("threat_level_id"),
            analysis=event.get("analysis"),
            date=date_val,
            org=event.get("Orgc", {}).get("name") if isinstance(event.get("Orgc"), dict) else None,
            raw=event,
        ).on_conflict_do_update(
            constraint="misp_events_pkey",
            set_={"info": event.get("info", "")[:1024], "raw": event},
        )
        await session.execute(stmt)
        events_count += 1

        for attr in event.get("Attribute", []):
            attr_type = attr.get("type", "")
            itype = _MISP_TYPE_MAP.get(attr_type)
            if not itype:
                continue
            raw_val = attr.get("value", "")
            if not raw_val:
                continue
            try:
                normalized = normalize_indicator(itype, raw_val)
            except Exception:
                continue

            stmt = insert(MISPIoc.__table__).values(
                id=uuid.uuid4(),
                event_id=event_id,
                type=itype.value,
                normalized_value=normalized,
                raw_value=raw_val,
                comment=attr.get("comment"),
                to_ids=bool(attr.get("to_ids")),
                raw=attr,
            ).on_conflict_do_update(
                constraint="uq_integrations_misp_iocs",
                set_={"comment": attr.get("comment"), "to_ids": bool(attr.get("to_ids")), "raw": attr},
            )
            await session.execute(stmt)
            iocs_count += 1

    return events_count, iocs_count


async def push_iocs_to_misp(
    session: AsyncSession,
    health: SourceHealthRepository,
    base_url: str,
    api_key: str,
    misp_event_id: str,
    ioc_collector_url: str,
    min_confidence: float = 0.85,
) -> int:
    """Push high-confidence IOCs from ioc-collector to a MISP event."""
    if not base_url or not api_key or not misp_event_id:
        log.info("misp push skipped: missing config")
        return 0

    headers = {"Authorization": api_key, "Accept": "application/json"}

    # Get IOCs we haven't pushed yet from ioc-collector
    already_pushed = await session.execute(
        select(MISPPush.local_indicator_id)
    )
    pushed_ids = {str(r[0]) for r in already_pushed}

    pushed = 0
    try:
        async with build_resilient_client(base_url=ioc_collector_url) as ioc_client:
            resp = await ioc_client.get(
                "/indicators",
                params={"min_confidence": min_confidence, "limit": 500},
                timeout=20,
            )
            resp.raise_for_status()
            indicators = resp.json()

        async with build_resilient_client(base_url=base_url, headers=headers) as misp_client:
            for ioc in indicators:
                ioc_id = ioc.get("id", "")
                if ioc_id in pushed_ids:
                    continue

                misp_type = _to_misp_type(ioc.get("type", ""))
                if not misp_type:
                    continue

                resp = await misp_client.post(
                    f"/attributes/add/{misp_event_id}",
                    json={"type": misp_type, "value": ioc.get("normalized_value", ""), "to_ids": True, "comment": "TIP auto-push"},
                    timeout=15,
                )
                if resp.status_code in (200, 201):
                    attr_id = str(resp.json().get("Attribute", {}).get("id", ""))
                    session.add(MISPPush(
                        local_indicator_id=uuid.UUID(ioc_id),
                        misp_event_id=misp_event_id,
                        misp_attribute_id=attr_id,
                    ))
                    pushed += 1

        await session.commit()
        log.info("misp_push pushed=%d", pushed)
    except Exception as exc:
        log.error("misp_push error=%s", exc)

    return pushed


def _to_misp_type(tip_type: str) -> str | None:
    return {
        "ip": "ip-dst",
        "domain": "domain",
        "url": "url",
        "md5": "md5",
        "sha1": "sha1",
        "sha256": "sha256",
    }.get(tip_type)
