"""
Fetches MITRE ATT&CK STIX bundles (enterprise + ICS + mobile) and upserts
actors (intrusion-sets), tools (tools + malware), and TTP relationships.
"""
import logging
import uuid
from datetime import date

import httpx
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tip_http import build_resilient_client
from tip_source_health import SourceHealthRepository

from app.models import Actor, ActorTool, ActorTTP, Tool

log = logging.getLogger(__name__)

STIX_URLS = {
    "enterprise": "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json",
    "ics": "https://raw.githubusercontent.com/mitre/cti/master/ics-attack/ics-attack.json",
    "mobile": "https://raw.githubusercontent.com/mitre/cti/master/mobile-attack/mobile-attack.json",
}


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


def _extract_text(obj: dict, field: str) -> str | None:
    val = obj.get(field)
    if isinstance(val, list):
        return val[0].get("value") if val else None
    return val


async def _fetch_bundle(source_key: str, url: str, client: httpx.AsyncClient) -> dict:
    resp = await client.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


async def sync_mitre_attack(session: AsyncSession, health: SourceHealthRepository) -> int:
    """Downloads all three ATT&CK bundles and upserts actors/tools/TTPs."""
    total = 0
    async with build_resilient_client() as client:
        for domain, url in STIX_URLS.items():
            source_name = f"mitre-attack-{domain}"
            try:
                bundle = await _fetch_bundle(source_name, url, client)
                count = await _process_bundle(session, bundle, source_name)
                await health.mark_success(source_name)
                total += count
                log.info("mitre_attack domain=%s objects_processed=%d", domain, count)
            except Exception as exc:
                log.error("mitre_attack domain=%s error=%s", domain, exc)
                await health.mark_failure(source_name, str(exc))

    return total


async def _process_bundle(session: AsyncSession, bundle: dict, source_name: str) -> int:
    objects = bundle.get("objects", [])

    # Index techniques for relationship resolution
    technique_map: dict[str, dict] = {}
    for obj in objects:
        if obj.get("type") in ("attack-pattern",):
            technique_map[obj["id"]] = obj

    # Upsert tools and malware first (they can be referenced by actors)
    tool_stix_to_db: dict[str, uuid.UUID] = {}
    for obj in objects:
        if obj.get("type") not in ("tool", "malware"):
            continue
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue
        db_id = await _upsert_tool(session, obj)
        tool_stix_to_db[obj["id"]] = db_id

    # Upsert actors (intrusion-sets)
    actor_stix_to_db: dict[str, uuid.UUID] = {}
    for obj in objects:
        if obj.get("type") != "intrusion-set":
            continue
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue
        db_id = await _upsert_actor(session, obj)
        actor_stix_to_db[obj["id"]] = db_id

    # Process relationships
    for obj in objects:
        if obj.get("type") != "relationship":
            continue
        rel_type = obj.get("relationship_type")
        src = obj.get("source_ref", "")
        tgt = obj.get("target_ref", "")

        if rel_type == "uses" and src in actor_stix_to_db:
            actor_db_id = actor_stix_to_db[src]
            if tgt in technique_map:
                tech = technique_map[tgt]
                await _upsert_actor_ttp(session, actor_db_id, tech, source_name)
            elif tgt in tool_stix_to_db:
                await _upsert_actor_tool(session, actor_db_id, tool_stix_to_db[tgt])

    await session.commit()
    return len(actor_stix_to_db)


async def _upsert_actor(session: AsyncSession, obj: dict) -> uuid.UUID:
    mitre_id = None
    for ext_ref in obj.get("external_references", []):
        if ext_ref.get("source_name") == "mitre-attack":
            mitre_id = ext_ref.get("external_id")
            break

    aliases = obj.get("aliases", [])
    if obj["name"] in aliases:
        aliases.remove(obj["name"])

    values = {
        "name": obj["name"],
        "aliases": aliases,
        "origin_country": obj.get("x_mitre_contributors", [None])[0] if obj.get("x_mitre_contributors") else None,
        "motivation": _extract_motivation(obj),
        "target_sectors": _extract_sectors(obj),
        "target_countries": [],
        "status": "inactive" if obj.get("x_mitre_deprecated") else "active",
        "raw": {k: v for k, v in obj.items() if k not in ("id", "type")},
    }

    # Try to find existing actor by mitre_id
    existing = None
    if mitre_id:
        result = await session.execute(
            select(Actor).where(Actor.mitre_id == mitre_id)
        )
        existing = result.scalar_one_or_none()

    if existing:
        for k, v in values.items():
            setattr(existing, k, v)
        return existing.id
    else:
        new_actor = Actor(id=uuid.uuid4(), mitre_id=mitre_id, **values)
        session.add(new_actor)
        await session.flush()
        return new_actor.id


async def _upsert_tool(session: AsyncSession, obj: dict) -> uuid.UUID:
    mitre_id = None
    for ext_ref in obj.get("external_references", []):
        if ext_ref.get("source_name") == "mitre-attack":
            mitre_id = ext_ref.get("external_id")
            break

    aliases = obj.get("x_mitre_aliases", [])
    if obj["name"] in aliases:
        aliases.remove(obj["name"])

    result = await session.execute(
        select(Tool).where(Tool.mitre_id == mitre_id) if mitre_id
        else select(Tool).where(Tool.name == obj["name"])
    )
    existing = result.scalar_one_or_none()

    values = {
        "name": obj["name"],
        "aliases": aliases,
        "type": obj["type"],
        "mitre_id": mitre_id,
        "description": obj.get("description"),
        "raw": {k: v for k, v in obj.items() if k not in ("id", "type")},
    }

    if existing:
        for k, v in values.items():
            setattr(existing, k, v)
        return existing.id
    else:
        new_tool = Tool(id=uuid.uuid4(), **values)
        session.add(new_tool)
        await session.flush()
        return new_tool.id


async def _upsert_actor_ttp(session: AsyncSession, actor_id: uuid.UUID, tech: dict, source: str) -> None:
    technique_id = None
    for ext_ref in tech.get("external_references", []):
        if ext_ref.get("source_name") == "mitre-attack":
            technique_id = ext_ref.get("external_id")
            break
    if not technique_id:
        return

    stmt = insert(ActorTTP.__table__).values(
        actor_id=actor_id,
        technique_id=technique_id,
        technique_name=tech.get("name", ""),
        sub_technique_id=None,
        confidence=0.80,
        source=source,
    ).on_conflict_do_update(
        constraint="pk_actors_actor_ttps",
        set_={"technique_name": tech.get("name", ""), "source": source},
    )
    await session.execute(stmt)


async def _upsert_actor_tool(session: AsyncSession, actor_id: uuid.UUID, tool_id: uuid.UUID) -> None:
    stmt = insert(ActorTool.__table__).values(
        actor_id=actor_id,
        tool_id=tool_id,
    ).on_conflict_do_nothing(constraint="pk_actors_actor_tools")
    await session.execute(stmt)


def _extract_motivation(obj: dict) -> list[str]:
    motivations = []
    for field in ("primary_motivation", "secondary_motivations", "goals"):
        val = obj.get(field)
        if not val:
            continue
        if isinstance(val, list):
            motivations.extend(str(v) for v in val)
        else:
            motivations.append(str(val))
    return list(dict.fromkeys(motivations))


def _extract_sectors(obj: dict) -> list[str]:
    sectors = obj.get("x_mitre_domains", [])
    if isinstance(sectors, str):
        sectors = [sectors]
    return sectors
