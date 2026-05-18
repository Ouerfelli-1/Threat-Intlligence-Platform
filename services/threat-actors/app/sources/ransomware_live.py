"""
Fetches ransomware groups and victims from ransomware.live API v2.

ransomware.live API endpoints used:
 - GET /v2/groups                  -> list of group summaries (name, captureddate, location, etc.)
 - GET /v2/group/{name}            -> full profile per group (description, profile, tor_urls, ...)
 - GET /v2/recentvictims           -> last ~200 victims across all groups
 - GET /v2/groupvictims/{name}     -> all historical victims for a single group

This module:
 1. Pulls every group via /groups and /group/{name} for richer fields
 2. Pulls victims (recent or full history)
 3. Recomputes denormalized aggregates on each group (victim_count, target_countries, target_sectors)
 4. Correlates each group with a MITRE actor if their names/aliases match
"""
import asyncio
import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tip_http import build_resilient_client
from tip_source_health import SourceHealthRepository

from app.models import Actor, RansomwareGroup, RansomwareVictim

log = logging.getLogger(__name__)

BASE_URL = "https://api.ransomware.live/v2"
SOURCE_NAME = "ransomware.live"


def _compute_dedup_key(group_id: uuid.UUID, victim_name: str, disclosed_at: datetime | None) -> str:
    iso = disclosed_at.isoformat(sep=" ") if disclosed_at else ""
    payload = f"{group_id}|{victim_name}|{iso}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_date(s) -> datetime | None:
    """Robust date parser. ransomware.live mixes formats:
        - ISO 8601 with offset:      2024-09-12T14:32:11Z
        - ISO 8601 with microseconds: 2024-09-12T14:32:11.123456
        - 'dd-MM-yyyy HH:MM'         12-09-2024 14:32
        - 'yyyy-MM-dd'               2024-09-12
        - bare numeric (epoch sec)
    """
    if s in (None, "", "null"):
        return None
    if isinstance(s, (int, float)):
        try:
            return datetime.fromtimestamp(float(s), tz=timezone.utc)
        except Exception:
            return None
    s = str(s).strip()
    if not s:
        return None
    # ISO with trailing Z
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(s[: len(fmt) + 6], fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def _normalize_name(s: str) -> str:
    """Lowercase, strip whitespace, collapse non-alphanumerics. Used for actor matching."""
    return re.sub(r"[^a-z0-9]+", "", s.lower())


async def sync_ransomware_groups(session: AsyncSession, health: SourceHealthRepository) -> int:
    """Pulls every group via /groups then enriches each with /group/{name}.
    Heavy on the first pull (~340 groups, ~340 API calls); cheap thereafter."""
    try:
        async with build_resilient_client(base_url=BASE_URL) as client:
            resp = await client.get("/groups", timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            summaries = payload if isinstance(payload, list) else []

            count = 0
            for idx, group_summary in enumerate(summaries):
                name = (group_summary.get("name") or "").strip()
                if not name:
                    continue
                profile = group_summary
                # Try richer profile via /group/{name}; tolerate failures
                try:
                    gresp = await client.get(f"/group/{name}", timeout=20)
                    if gresp.status_code == 200:
                        merged = gresp.json()
                        if isinstance(merged, dict):
                            # Profile endpoint sometimes returns a list-with-single-item
                            profile = {**group_summary, **merged}
                        elif isinstance(merged, list) and merged and isinstance(merged[0], dict):
                            profile = {**group_summary, **merged[0]}
                except Exception as exc:
                    log.warning("ransomware_live group_profile_failed group=%s err=%s", name, exc)

                await _upsert_group(session, profile)
                count += 1
                # Gentle pacing — ~340 calls
                if idx % 25 == 0:
                    await session.commit()
                    log.info("ransomware_live groups progress=%d/%d", idx + 1, len(summaries))
                await asyncio.sleep(0.05)

        await session.commit()
        await health.mark_success(SOURCE_NAME)
        log.info("ransomware_live groups_synced=%d", count)
        return count
    except Exception as exc:
        log.error("ransomware_live groups error=%s", exc)
        await health.mark_failure(SOURCE_NAME, str(exc))
        return 0


async def sync_ransomware_victims(session: AsyncSession, health: SourceHealthRepository, limit: int = 500) -> int:
    """Fetches recent victims only (fast path; ~200 latest)."""
    try:
        async with build_resilient_client(base_url=BASE_URL) as client:
            resp = await client.get("/recentvictims", timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            victims = payload if isinstance(payload, list) else []

        count = 0
        for victim_data in victims[:limit]:
            await _upsert_victim(session, victim_data)
            count += 1

        await session.commit()
        await _recompute_group_aggregates(session)
        await health.mark_success(f"{SOURCE_NAME}-victims")
        log.info("ransomware_live victims_synced=%d", count)
        return count
    except Exception as exc:
        log.error("ransomware_live victims error=%s", exc)
        await health.mark_failure(f"{SOURCE_NAME}-victims", str(exc))
        return 0


async def sync_ransomware_victims_full(session: AsyncSession, health: SourceHealthRepository) -> int:
    """Full historical pull. ~80k+ victims; heavy. Use only on first-boot seed."""
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
                    victims = vresp.json()
                    if not isinstance(victims, list):
                        continue
                except Exception as exc:
                    log.warning("ransomware_live group_victims_failed group=%s error=%s", name, exc)
                    continue

                for v in victims:
                    await _upsert_victim(session, v)
                    total += 1

                await session.commit()
                if idx % 20 == 0:
                    log.info(
                        "ransomware_live full_sync progress group=%d/%d victims_so_far=%d",
                        idx + 1, len(groups), total,
                    )
                await asyncio.sleep(0.1)

        await _recompute_group_aggregates(session)
        await health.mark_success(f"{SOURCE_NAME}-victims-full")
        log.info("ransomware_live full_sync_complete total_victims=%d", total)
        return total
    except Exception as exc:
        log.error("ransomware_live full_sync error=%s", exc)
        await health.mark_failure(f"{SOURCE_NAME}-victims-full", str(exc))
        return total


# ──────────────────────────────────────────────────────────────────────────────
# Upserts
# ──────────────────────────────────────────────────────────────────────────────

def _coerce_list(val) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(v).strip() for v in val if v]
    if isinstance(val, str) and val.strip():
        return [val.strip()]
    return []


def _extract_iocs(data: dict) -> dict:
    """ransomware.live varies; harvest anything that looks like IOC fields into one bag."""
    out: dict = {}
    for k in ("urls", "tor_urls", "onions", "leak_urls"):
        v = _coerce_list(data.get(k))
        if v:
            out.setdefault("tor_urls", []).extend(v)
    for k in ("c2", "c2s", "c2_servers", "command_and_control"):
        v = _coerce_list(data.get(k))
        if v:
            out.setdefault("c2", []).extend(v)
    for k in ("hashes", "samples", "iocs"):
        v = data.get(k)
        if v:
            out[k] = v
    return out


async def _upsert_group(session: AsyncSession, data: dict) -> uuid.UUID:
    name = (data.get("name") or "").strip()
    if not name:
        return uuid.uuid4()

    result = await session.execute(
        select(RansomwareGroup).where(RansomwareGroup.name == name)
    )
    existing = result.scalar_one_or_none()

    aliases = _coerce_list(data.get("aliases") or data.get("akas"))
    # ransomware.live `locations` is a list of dicts: {fqdn, slug, title, type, available, enabled}.
    # We want:
    #   tor_urls       -> the actual .onion URLs (slug field, falling back to fqdn)
    #   locations      -> human-friendly labels (title field)
    raw_locations = data.get("locations")
    tor_urls: list[str] = []
    location_strings: list[str] = []
    if isinstance(raw_locations, list):
        for loc in raw_locations:
            if isinstance(loc, str):
                tor_urls.append(loc)
                location_strings.append(loc)
            elif isinstance(loc, dict):
                url = loc.get("slug") or loc.get("fqdn")
                if url:
                    tor_urls.append(str(url))
                label = loc.get("title") or loc.get("fqdn") or loc.get("slug")
                if label:
                    location_strings.append(str(label))
    # Other plausible plain-string fields
    for k in ("urls", "tor_urls", "onions"):
        for v in _coerce_list(data.get(k)):
            if v and v not in tor_urls:
                tor_urls.append(v)

    domains = _coerce_list(data.get("domains"))
    description = (
        data.get("description")
        or data.get("profile")
        or data.get("meta")
        or None
    )
    if isinstance(description, dict):
        # Some MITRE-style dict; pick whichever text-field exists
        description = (
            description.get("description")
            or description.get("notes")
            or None
        )

    profile_url = (
        data.get("profile_link")
        or data.get("profile_url")
        or data.get("url")
        or None
    )

    first_seen = _parse_date(
        data.get("first_seen")
        or data.get("captureddate")
        or (data.get("meta", {}) if isinstance(data.get("meta"), dict) else {}).get("first_seen")
    )
    last_seen = _parse_date(
        data.get("last_seen")
        or data.get("lastseen")
        or (data.get("meta", {}) if isinstance(data.get("meta"), dict) else {}).get("last_seen")
    )

    iocs = _extract_iocs(data)

    values = {
        "name": name,
        "aliases": aliases,
        "status": (data.get("status") or "active").lower() or "active",
        "first_seen": first_seen.date() if first_seen else None,
        "last_seen": last_seen.date() if last_seen else None,
        "variants": _coerce_list(data.get("variants")),
        "leak_site_url": (
            data.get("url")
            or (location_strings[0] if location_strings else None)
            or None
        ),
        "ransom_range": {
            "min": data.get("ransom_min"),
            "max": data.get("ransom_max"),
        },
        "raw": data,
        "description": description if isinstance(description, str) else None,
        "profile_url": profile_url if isinstance(profile_url, str) else None,
        "tor_urls": tor_urls,
        "domains": domains,
        "locations": location_strings,
        "iocs": iocs,
    }

    if existing:
        for k, v in values.items():
            setattr(existing, k, v)
        return existing.id

    new_group = RansomwareGroup(id=uuid.uuid4(), **values)
    session.add(new_group)
    await session.flush()
    return new_group.id


async def _upsert_victim(session: AsyncSession, data: dict) -> None:
    """Insert or refresh a victim row, idempotent via dedup_key."""
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
            tor_urls=[],
            domains=[],
            locations=[],
            iocs={},
            target_countries=[],
            target_sectors=[],
        )
        session.add(group)
        await session.flush()

    victim_name = (
        data.get("victim")
        or data.get("post_title")
        or data.get("domain")
        or "unknown"
    )

    # ransomware.live victim date precedence:
    #   discovered  -> when the group posted on their leak site
    #   attackdate  -> alleged compromise date (analyst-provided)
    #   published   -> general fallback
    disclosed_at = _parse_date(
        data.get("discovered")
        or data.get("attackdate")
        or data.get("published")
        or data.get("date")
        or data.get("post_date")
    )

    dedup_key = _compute_dedup_key(group.id, victim_name, disclosed_at)

    stmt = insert(RansomwareVictim.__table__).values(
        id=uuid.uuid4(),
        group_id=group.id,
        victim_name=victim_name,
        sector=data.get("activity") or data.get("sector"),
        country=data.get("country"),
        disclosed_at=disclosed_at,
        source=SOURCE_NAME,
        raw=data,
        dedup_key=dedup_key,
    ).on_conflict_do_update(
        index_elements=["dedup_key"],
        set_={
            "sector": data.get("activity") or data.get("sector"),
            "country": data.get("country"),
            "raw": data,
        },
    )
    await session.execute(stmt)


# ──────────────────────────────────────────────────────────────────────────────
# Aggregates: keep ransomware_groups.victim_count/target_countries/target_sectors
# in sync with the actual victim rows so the UI can show real numbers without
# a per-row aggregation query.
# ──────────────────────────────────────────────────────────────────────────────

async def _recompute_group_aggregates(session: AsyncSession) -> None:
    rows = (await session.execute(
        select(RansomwareGroup.id, RansomwareGroup.name)
    )).all()

    for group_id, group_name in rows:
        # Total victims
        vc = await session.scalar(
            select(func.count()).select_from(RansomwareVictim).where(
                RansomwareVictim.group_id == group_id
            )
        )
        # Distinct countries / sectors
        countries = (await session.execute(
            select(RansomwareVictim.country)
            .where(RansomwareVictim.group_id == group_id)
            .where(RansomwareVictim.country.isnot(None))
            .distinct()
        )).scalars().all()
        sectors = (await session.execute(
            select(RansomwareVictim.sector)
            .where(RansomwareVictim.group_id == group_id)
            .where(RansomwareVictim.sector.isnot(None))
            .distinct()
        )).scalars().all()
        # Earliest / latest victim observation (refines group-level first/last)
        first = await session.scalar(
            select(func.min(RansomwareVictim.disclosed_at)).where(
                RansomwareVictim.group_id == group_id
            )
        )
        last = await session.scalar(
            select(func.max(RansomwareVictim.disclosed_at)).where(
                RansomwareVictim.group_id == group_id
            )
        )

        update_values: dict = {
            "victim_count": int(vc or 0),
            "target_countries": [c for c in countries if c],
            "target_sectors": [s for s in sectors if s],
        }
        if first:
            update_values["first_seen"] = first.date()
        if last:
            update_values["last_seen"] = last.date()

        await session.execute(
            update(RansomwareGroup)
            .where(RansomwareGroup.id == group_id)
            .values(**update_values)
        )

    await session.commit()


# ──────────────────────────────────────────────────────────────────────────────
# Correlation: ransomware group <-> MITRE actor
# Strategy: match on normalized name OR on intersection of aliases.
# Several MITRE intrusion-sets correspond to ransomware groups (BlackCat/ALPHV,
# REvil/Sodinokibi, LockBit, Conti, etc). For groups without a MITRE entry the
# actor_id stays NULL — that's fine.
# ──────────────────────────────────────────────────────────────────────────────

async def correlate_groups_to_actors(session: AsyncSession) -> int:
    """Two passes:
      1. Link every ransomware group to a matching MITRE actor (by normalized name / alias).
      2. For ransomware groups WITHOUT a MITRE match, create a synthetic Actor record
         so the unified actor list contains every operationally-relevant adversary,
         not just the ones MITRE has formally documented. The synthetic actor's
         mitre_id stays NULL; if a future MITRE refresh introduces the same name,
         _upsert_actor's name-fallback path will merge them by setting mitre_id.

    Returns the count of groups that received (or kept) an actor_id link.
    """
    actors = (await session.execute(select(Actor))).scalars().all()
    by_norm: dict[str, uuid.UUID] = {}
    for a in actors:
        by_norm[_normalize_name(a.name)] = a.id
        for alias in (a.aliases or []):
            by_norm.setdefault(_normalize_name(alias), a.id)

    groups = (await session.execute(select(RansomwareGroup))).scalars().all()
    linked = 0
    created = 0
    for g in groups:
        candidates: list[str] = [g.name] + list(g.aliases or [])
        match: uuid.UUID | None = None
        for c in candidates:
            n = _normalize_name(c)
            if not n:
                continue
            if n in by_norm:
                match = by_norm[n]
                break

        if match is not None:
            if g.actor_id != match:
                g.actor_id = match
            linked += 1
            continue

        # No MITRE match. If we've already created a synthetic actor for this
        # group on a prior run, keep it. Otherwise create one now from the
        # group's enriched data so the actor list shows it.
        if g.actor_id is not None:
            # Existing link (probably synthetic from a prior run) — keep it
            linked += 1
            continue

        new_id = uuid.uuid4()
        new_actor = Actor(
            id=new_id,
            mitre_id=None,
            name=g.name,
            aliases=list(g.aliases or []),
            origin_country=None,
            description=g.description,
            # Ransomware operators are financially motivated by default.
            motivation=["financial-gain"],
            active_since=g.first_seen,
            last_seen=g.last_seen,
            target_sectors=list(g.target_sectors or []),
            target_countries=list(g.target_countries or []),
            status=g.status or "active",
            raw={
                "_source": "ransomware.live",
                "ransomware_group_id": str(g.id),
                "victim_count": g.victim_count,
            },
            analyst_status="unreviewed",
        )
        session.add(new_actor)
        await session.flush()
        g.actor_id = new_id
        # Make this new actor visible to subsequent groups with overlapping aliases
        by_norm[_normalize_name(g.name)] = new_id
        for alias in (g.aliases or []):
            by_norm.setdefault(_normalize_name(alias), new_id)
        created += 1
        linked += 1

    await session.commit()
    log.info(
        "ransomware_live actor_correlation linked=%d/%d synthetic_created=%d",
        linked, len(groups), created,
    )
    return linked
