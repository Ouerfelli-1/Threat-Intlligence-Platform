"""
Fetches MITRE ATT&CK STIX bundles (enterprise + ICS + mobile) and upserts
actors (intrusion-sets), tools (tools + malware), and TTP relationships.

Field-mapping notes:
 - `description` -> persisted to `actors.description` (MITRE's own actor profile text)
 - `aliases` -> first item is the canonical name; remaining entries become aliases
 - `created` (STIX) -> approximate active_since
 - `modified` (STIX) -> approximate last_seen
 - `origin_country` is left NULL by default. MITRE does NOT store this in STIX
   intrusion-set objects. We only set it if `x_mitre_attributed_country` is
   present (custom MITRE field on some entries).
 - `target_sectors` is NOT taken from `x_mitre_domains` (those are kill-chain
   domains: enterprise / ics / mobile, not industries). Left empty unless we
   can infer from description.
"""
import logging
import re
import uuid
from datetime import date

import httpx
from sqlalchemy import select
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

# Keywords -> normalized sector tags. Used to scrape "target_sectors" from
# MITRE's free-text description when no structured field exists.
_SECTOR_KEYWORDS = {
    "finance": ["financial", "bank", "banking", "fintech", "atm", "swift"],
    "government": ["government", "ministry", "diplomat", "embassy", "state agencies"],
    "defense": ["defense", "defence", "military", "aerospace", "weapon"],
    "energy": ["energy", "oil", "gas", "utility", "utilities", "electric grid", "power grid"],
    "telecom": ["telecommunication", "telecom", "isp", "internet service provider"],
    "healthcare": ["health", "hospital", "pharmaceutical", "medical"],
    "technology": ["technology firm", "software vendor", "cloud provider", "msp"],
    "education": ["university", "academic", "research institution", "education"],
    "retail": ["retail", "e-commerce", "ecommerce", "point of sale", "pos"],
    "manufacturing": ["manufactur", "industrial", "automotive", "factory"],
    "media": ["media", "press", "journalist", "broadcaster"],
    "ngo": ["ngo", "non-governmental", "non-profit", "nonprofit", "human rights"],
    "transportation": ["aviation", "airline", "maritime", "shipping", "logistics"],
    "critical_infrastructure": ["critical infrastructure", "scada", "ot networks"],
}

# Country regex map: matches both ISO names and common synonyms.
# Used to scrape target countries from description prose.
_COUNTRY_KEYWORDS = {
    "United States": ["united states", "u\\.s\\.", " us ", "american", "usa"],
    "United Kingdom": ["united kingdom", "u\\.k\\.", "british", " uk "],
    "Russia": ["russia", "russian"],
    "China": ["china", "chinese"],
    "Iran": ["iran", "iranian"],
    "North Korea": ["north korea", "north korean", "dprk"],
    "Israel": ["israel", "israeli"],
    "Ukraine": ["ukraine", "ukrainian"],
    "France": ["france", "french"],
    "Germany": ["germany", "german"],
    "Saudi Arabia": ["saudi arabia", "saudi"],
    "Turkey": ["turkey", "turkish"],
    "India": ["india", "indian"],
    "Japan": ["japan", "japanese"],
    "South Korea": ["south korea", "south korean", " rok "],
    "Australia": ["australia", "australian"],
    "Canada": ["canada", "canadian"],
}


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


def _scrape_sectors(description: str | None) -> list[str]:
    if not description:
        return []
    desc_low = description.lower()
    out: list[str] = []
    for sector, keywords in _SECTOR_KEYWORDS.items():
        if any(k in desc_low for k in keywords):
            out.append(sector)
    return out


def _scrape_countries(description: str | None) -> list[str]:
    if not description:
        return []
    desc_low = description.lower()
    out: list[str] = []
    for country, patterns in _COUNTRY_KEYWORDS.items():
        if any(re.search(p, desc_low) for p in patterns):
            out.append(country)
    return out


def _extract_motivation(obj: dict) -> list[str]:
    """STIX 2.1 motivation fields. MITRE rarely populates these on intrusion-sets,
    so most actors will return an empty list — that's expected and correct."""
    motivations: list[str] = []
    for field in ("primary_motivation", "secondary_motivations", "goals"):
        val = obj.get(field)
        if not val:
            continue
        if isinstance(val, list):
            motivations.extend(str(v).strip().lower() for v in val if v)
        else:
            motivations.append(str(val).strip().lower())
    return list(dict.fromkeys(motivations))


def _extract_origin_country(obj: dict) -> str | None:
    """MITRE's STIX bundle does not encode actor origin in a stable structured
    field. The historical bug was harvesting x_mitre_contributors which lists
    credit names. We leave origin null unless a structured field is present."""
    for field in (
        "x_mitre_attributed_country",       # speculative, not actually in MITRE
        "country",                          # never in upstream MITRE bundles
    ):
        val = obj.get(field)
        if isinstance(val, str) and val:
            return val.strip()
        if isinstance(val, list) and val and isinstance(val[0], str):
            return val[0].strip()
    return None


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
                log.info("mitre_attack domain=%s actors_processed=%d", domain, count)
            except Exception as exc:
                log.error("mitre_attack domain=%s error=%s", domain, exc)
                await health.mark_failure(source_name, str(exc))

    return total


async def _process_bundle(session: AsyncSession, bundle: dict, source_name: str) -> int:
    objects = bundle.get("objects", [])

    technique_map: dict[str, dict] = {}
    for obj in objects:
        if obj.get("type") in ("attack-pattern",):
            technique_map[obj["id"]] = obj

    # Upsert tools / malware first
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

    aliases = list(obj.get("aliases", []) or [])
    canonical_name = obj.get("name", "").strip()
    # MITRE puts the canonical name as the first alias; trim duplicates.
    aliases = [a for a in aliases if a and a != canonical_name]

    description = obj.get("description") or None
    scraped_sectors = _scrape_sectors(description)
    scraped_countries = _scrape_countries(description)

    values = {
        "name": canonical_name,
        "aliases": aliases,
        "origin_country": _extract_origin_country(obj),
        "description": description,
        "motivation": _extract_motivation(obj),
        "active_since": _parse_date(obj.get("first_seen") or obj.get("created")),
        "last_seen": _parse_date(obj.get("last_seen") or obj.get("modified")),
        "target_sectors": scraped_sectors,
        "target_countries": scraped_countries,
        "status": "inactive" if obj.get("x_mitre_deprecated") else "active",
        "raw": {k: v for k, v in obj.items() if k not in ("id", "type")},
    }

    existing = None
    if mitre_id:
        result = await session.execute(select(Actor).where(Actor.mitre_id == mitre_id))
        existing = result.scalar_one_or_none()

    if existing is None:
        # Fall back to name match (deduplicates pre-existing rows that lack mitre_id)
        result = await session.execute(select(Actor).where(Actor.name == canonical_name))
        existing = result.scalar_one_or_none()
        if existing and mitre_id and not existing.mitre_id:
            existing.mitre_id = mitre_id

    if existing:
        for k, v in values.items():
            setattr(existing, k, v)
        return existing.id

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

    aliases = list(obj.get("x_mitre_aliases", []) or [])
    canonical_name = obj.get("name", "").strip()
    aliases = [a for a in aliases if a and a != canonical_name]

    result = await session.execute(
        select(Tool).where(Tool.mitre_id == mitre_id) if mitre_id
        else select(Tool).where(Tool.name == canonical_name)
    )
    existing = result.scalar_one_or_none()

    values = {
        "name": canonical_name,
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
