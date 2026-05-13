"""
Fetches ransomware groups and victims from ransomware.live API.

Two pull modes:
 - sync_ransomware_victims(): last ~100 recent victims (fast, periodic refresh)
 - sync_ransomware_victims_full(): full history, all groups (heavy, first-boot seed)
"""
import hashlib
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tip_http import build_resilient_client
from tip_source_health import SourceHealthRepository

from app.models import RansomwareGroup, RansomwareVictim


def _compute_dedup_key(group_id: uuid.UUID, victim_name: str, disclosed_at: datetime | None) -> str:
    """Deterministic SHA256 for victim dedup. Matches migration 0002 backfill."""
    iso = disclosed_at.isoformat(sep=" ") if disclosed_at else ""
    payload = f"{group_id}|{victim_name}|{iso}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

log = logging.getLogger(__name__)

BASE_URL = "https://api.ransomware.live/v2"
SOURCE_NAME = "ransomware.live"


def _parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:len(fmt)], fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


async def sync_ransomware_groups(session: AsyncSession, health: SourceHealthRepository) -> int:
    try:
        async with build_resilient_client(base_url=BASE_URL) as client:
            resp = await client.get("/groups", timeout=30)
            resp.raise_for_status()
            groups = resp.json() if isinstance(resp.json(), list) else []

        count = 0
        for group_data in groups:
            await _upsert_group(session, group_data)
            count += 1

        await session.commit()
        await health.mark_success(SOURCE_NAME)
        log.info("ransomware_live groups_synced=%d", count)
        return count
    except Exception as exc:
        log.error("ransomware_live groups error=%s", exc)
        await health.mark_failure(SOURCE_NAME, str(exc))
        return 0


async def sync_ransomware_victims(session: AsyncSession, health: SourceHealthRepository, limit: int = 500) -> int:
    """Fetches recent victims only (fast path; ~100 latest)."""
    try:
        async with build_resilient_client(base_url=BASE_URL) as client:
            resp = await client.get("/recentvictims", timeout=30)
            resp.raise_for_status()
            victims = resp.json() if isinstance(resp.json(), list) else []

        count = 0
        for victim_data in victims[:limit]:
            await _upsert_victim(session, victim_data)
            count += 1

        await session.commit()
        await health.mark_success(f"{SOURCE_NAME}-victims")
        log.info("ransomware_live victims_synced=%d", count)
        return count
    except Exception as exc:
        log.error("ransomware_live victims error=%s", exc)
        await health.mark_failure(f"{SOURCE_NAME}-victims", str(exc))
        return 0


async def sync_ransomware_victims_full(session: AsyncSession, health: SourceHealthRepository) -> int:
    """Full historical pull: iterate every group and fetch all its victims.

    Heavy operation — call only on first-boot seed or for periodic full reconciliation.
    ransomware.live serves victims grouped by attacker. ~345 groups, ~80k+ victims total.
    """
    import asyncio
    total = 0
    try:
        async with build_resilient_client(base_url=BASE_URL) as client:
            resp = await client.get("/groups", timeout=30)
            resp.raise_for_status()
            groups = resp.json() if isinstance(resp.json(), list) else []

            for idx, group_data in enumerate(groups):
                name = (group_data.get("name") or "").strip()
                if not name:
                    continue
                try:
                    vresp = await client.get(f"/groupvictims/{name}", timeout=30)
                    if vresp.status_code != 200:
                        continue
                    payload = vresp.json()
                    victims = payload if isinstance(payload, list) else []
                except Exception as exc:
                    log.warning("ransomware_live group_victims_failed group=%s error=%s", name, exc)
                    continue

                for v in victims:
                    await _upsert_victim(session, v)
                    total += 1

                # Commit per-group to avoid one huge transaction
                await session.commit()
                if idx % 20 == 0:
                    log.info("ransomware_live full_sync progress group=%d/%d victims_so_far=%d", idx + 1, len(groups), total)
                # Gentle pacing — ransomware.live tolerates this but no need to hammer
                await asyncio.sleep(0.1)

        await health.mark_success(f"{SOURCE_NAME}-victims-full")
        log.info("ransomware_live full_sync_complete total_victims=%d", total)
        return total
    except Exception as exc:
        log.error("ransomware_live full_sync error=%s", exc)
        await health.mark_failure(f"{SOURCE_NAME}-victims-full", str(exc))
        return total


async def _upsert_group(session: AsyncSession, data: dict) -> uuid.UUID:
    name = data.get("name", "").strip()
    if not name:
        return uuid.uuid4()

    result = await session.execute(
        select(RansomwareGroup).where(RansomwareGroup.name == name)
    )
    existing = result.scalar_one_or_none()

    values = {
        "name": name,
        "aliases": data.get("aliases", []) or [],
        "status": data.get("status", "active") or "active",
        "first_seen": _parse_date(data.get("first_seen")),
        "last_seen": _parse_date(data.get("last_seen")),
        "variants": data.get("variants", []) or [],
        "leak_site_url": data.get("url"),
        "ransom_range": {
            "min": data.get("ransom_min"),
            "max": data.get("ransom_max"),
        },
        "raw": data,
    }

    if existing:
        for k, v in values.items():
            setattr(existing, k, v)
        return existing.id
    else:
        new_group = RansomwareGroup(id=uuid.uuid4(), **values)
        session.add(new_group)
        await session.flush()
        return new_group.id


async def _upsert_victim(session: AsyncSession, data: dict) -> None:
    """Insert or refresh a victim row, idempotent via dedup_key."""
    # ransomware.live /recentvictims fields: group, victim, activity, country,
    # discovered, attackdate, claim_url, description, domain, screenshot, url, …
    group_name = (data.get("group") or data.get("group_name") or "").strip()
    if not group_name:
        return

    result = await session.execute(
        select(RansomwareGroup).where(RansomwareGroup.name == group_name)
    )
    group = result.scalar_one_or_none()
    if not group:
        group = RansomwareGroup(
            id=uuid.uuid4(),
            name=group_name,
            aliases=[],
            status="active",
            variants=[],
            ransom_range={},
            raw={},
        )
        session.add(group)
        await session.flush()

    victim_name = data.get("victim") or data.get("domain") or "unknown"
    disclosed_at = _parse_date(
        data.get("discovered") or data.get("attackdate") or data.get("published") or data.get("date")
    )
    dedup_key = _compute_dedup_key(group.id, victim_name, disclosed_at)

    # ON CONFLICT DO UPDATE keeps the latest sector/country/raw payload
    # without inserting duplicate rows for the same victim/group/date triple.
    stmt = insert(RansomwareVictim.__table__).values(
        id=uuid.uuid4(),
        group_id=group.id,
        victim_name=victim_name,
        sector=data.get("activity"),
        country=data.get("country"),
        disclosed_at=disclosed_at,
        source=SOURCE_NAME,
        raw=data,
        dedup_key=dedup_key,
    ).on_conflict_do_update(
        index_elements=["dedup_key"],
        set_={
            "sector": data.get("activity"),
            "country": data.get("country"),
            "raw": data,
        },
    )
    await session.execute(stmt)
