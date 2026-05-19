import asyncio
import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_ai import (
    LiteLLMError,
    LiteLLMRateLimitError,
    LiteLLMRequestTooLargeError,
    build_ai_client,
    generate_structured,
)
from tip_auth import current_user, require_permission
from tip_common import NotFoundError
from tip_db import get_session

from app.db import get_session_factory
from app.models import Actor, ActorInsight, ActorTool, ActorTTP, RansomwareGroup, Tool
from app.prompts import HUNTING_PROMPT, IOC_EXTRACTION_PROMPT, PROMPT_VERSION
from app.schemas import (
    ActorCreateManual,
    ActorDetailOut,
    ActorInsightOut,
    ActorList,
    ActorOut,
    AnalyzeRequest,
    AnalystStatusUpdate,
    InsightOverrideIn,
    RansomwareGroupOut,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/actors", tags=["actors"])


async def _session_dep():
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


@router.get(
    "",
    response_model=ActorList,
    dependencies=[Depends(require_permission("actors:read"))],
)
async def list_actors(
    session: SessionDep,
    q: str | None = Query(None, description="Free-text search across name + aliases + description"),
    name: str | None = Query(None, description="Substring match on name (legacy alias for q)"),
    sector: str | None = Query(None),
    country: str | None = Query(None),
    motivation: str | None = Query(None),
    status: str | None = Query(None),
    include_not_relevant: bool = Query(False),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    stmt = select(Actor)
    if not include_not_relevant:
        stmt = stmt.where(Actor.analyst_status != "not_relevant")

    search_term = q or name
    if search_term:
        like = f"%{search_term}%"
        # Match identity fields only (name / aliases / mitre id). Description
        # matching was too greedy — searching "lockbit" pulled in every actor
        # whose profile mentioned LockBit as a related group. If a description
        # search is ever wanted, expose it as a separate query parameter.
        stmt = stmt.where(
            or_(
                Actor.name.ilike(like),
                func.array_to_string(Actor.aliases, ",").ilike(like),
                Actor.mitre_id.ilike(like),
            )
        )
    if sector:
        stmt = stmt.where(Actor.target_sectors.any(sector))
    if country:
        stmt = stmt.where(Actor.target_countries.any(country))
    if motivation:
        stmt = stmt.where(Actor.motivation.any(motivation))
    if status:
        stmt = stmt.where(Actor.status == status)

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Actor.name).offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return ActorList(items=[ActorOut.model_validate(r) for r in rows], total=total)


@router.get(
    "/{actor_id}",
    response_model=ActorDetailOut,
    dependencies=[Depends(require_permission("actors:read"))],
)
async def get_actor(actor_id: UUID, session: SessionDep):
    result = await session.execute(select(Actor).where(Actor.id == actor_id))
    actor = result.scalar_one_or_none()
    if not actor:
        raise NotFoundError(f"Actor {actor_id} not found")

    ttps_result = await session.execute(
        select(ActorTTP).where(ActorTTP.actor_id == actor_id).order_by(ActorTTP.technique_id)
    )
    tools_result = await session.execute(
        select(Tool).join(ActorTool, Tool.id == ActorTool.tool_id).where(ActorTool.actor_id == actor_id)
    )
    rg_result = await session.execute(
        select(RansomwareGroup).where(RansomwareGroup.actor_id == actor_id).order_by(RansomwareGroup.name)
    )

    return ActorDetailOut(
        **ActorOut.model_validate(actor).model_dump(),
        ttps=ttps_result.scalars().all(),
        tools=tools_result.scalars().all(),
        ransomware_groups=[RansomwareGroupOut.model_validate(g) for g in rg_result.scalars().all()],
    )


@router.post(
    "",
    response_model=ActorOut,
    status_code=201,
    dependencies=[Depends(require_permission("actors:write"))],
)
async def create_actor_manual(body: ActorCreateManual, session: SessionDep):
    """Analyst-created actor entry (mitre_id optional)."""
    actor = Actor(
        id=_uuid.uuid4(),
        name=body.name,
        mitre_id=body.mitre_id,
        aliases=body.aliases,
        origin_country=body.origin_country,
        description=body.description,
        motivation=body.motivation,
        target_sectors=body.target_sectors,
        target_countries=body.target_countries,
        analyst_status="reviewed",
    )
    session.add(actor)
    await session.flush()
    return ActorOut.model_validate(actor)


@router.patch(
    "/{actor_id}/status",
    response_model=ActorOut,
    dependencies=[Depends(require_permission("actors:write"))],
)
async def update_actor_status(actor_id: UUID, body: AnalystStatusUpdate, session: SessionDep):
    result = await session.execute(select(Actor).where(Actor.id == actor_id))
    actor = result.scalar_one_or_none()
    if not actor:
        raise NotFoundError(f"Actor {actor_id} not found")
    actor.analyst_status = body.analyst_status
    await session.flush()
    return ActorOut.model_validate(actor)


@router.get(
    "/{actor_id}/insight",
    response_model=ActorInsightOut,
    dependencies=[Depends(require_permission("actors:read"))],
)
async def get_actor_insight(actor_id: UUID, session: SessionDep):
    result = await session.execute(
        select(ActorInsight).where(ActorInsight.actor_id == actor_id)
    )
    insight = result.scalar_one_or_none()
    if not insight:
        raise NotFoundError(f"No insight for actor {actor_id}")
    return insight


@router.put(
    "/{actor_id}/insight/override",
    response_model=ActorInsightOut,
    dependencies=[Depends(require_permission("actors:write"))],
)
async def override_actor_insight(actor_id: UUID, body: InsightOverrideIn, session: SessionDep):
    result = await session.execute(
        select(ActorInsight).where(ActorInsight.actor_id == actor_id)
    )
    insight = result.scalar_one_or_none()
    if not insight:
        raise NotFoundError(f"No insight for actor {actor_id}")
    insight.analyst_override = body.analyst_override
    await session.flush()
    return ActorInsightOut.model_validate(insight)


# ── AI insight generation (same shape as threat-intel) ─────────────────────
# Threat-actors uses the exact same three-leg analyzer as threat-intel so the
# frontend can reuse the InsightView component verbatim and analysts get the
# same hunting-hypothesis + IOC + attack-flow output when pivoting from a
# threat to its author actor.

_SMART_MODEL_DEFAULTS = [
    "github/gpt-5-chat",
    "github/gpt-4.1",
    "github/gpt-4o",
    "anthropic/claude-3-5-sonnet-20241022",
]


class _ExtractedIOC(BaseModel):
    type: str
    value: str
    context: str = ""
    confidence: str = "medium"


class _IocsOut(BaseModel):
    iocs_extracted: list[_ExtractedIOC] = []


class _KeyArtifact(BaseModel):
    name: str
    note: str = ""


class _HuntingOut(BaseModel):
    hypothesis: str
    wazuh_rule: str = ""
    key_artifacts: list[_KeyArtifact] = []
    mitre_techniques: list[str] = []


def _smart_client(request: Request, override_model: str | None):
    """Build an ad-hoc AI client for the smart-tier model (gpt-5-chat first).

    Same pattern as threat-intel — walk `_SMART_MODEL_DEFAULTS` and pick
    the first one whose provider key is present in the secrets vault.
    """
    from copy import copy
    settings = request.app.state.settings
    secrets = getattr(request.app.state, "ai_secrets", {}) or {}

    chosen = override_model
    if not chosen:
        for m in _SMART_MODEL_DEFAULTS:
            provider_key = {
                "github/": "GITHUB_API_KEY",
                "anthropic/": "ANTHROPIC_API_KEY",
                "openai/": "OPENAI_API_KEY",
                "groq/": "GROQ_API_KEY",
                "gemini/": "GEMINI_API_KEY",
            }
            need = next((k for prefix, k in provider_key.items() if m.startswith(prefix)), None)
            if need is None or secrets.get(need):
                chosen = m
                break

    smart_settings = copy(settings)
    smart_settings.ai_primary_model = chosen or settings.ai_primary_model
    return build_ai_client(secrets, smart_settings)


@router.post(
    "/{actor_id}/analyze",
    response_model=ActorInsightOut,
    dependencies=[Depends(require_permission("actors:write"))],
)
async def analyze_actor(
    actor_id: UUID,
    request: Request,
    body: AnalyzeRequest | None = None,
    session: SessionDep = None,  # type: ignore[assignment]
) -> ActorInsightOut:
    """Generate a hunter-ready insight for a threat actor.

    Same three-leg pipeline as threat-intel:
      1. IOC extraction from the actor profile blob.
      2. Hunting hypothesis (hypothesis + wazuh rule + key artifacts + TTPs).
      3. Attack flow via the flowviz service.

    Cache-first by default — re-using a saved row at the current
    PROMPT_VERSION unless the analyst sends `force=true` (the
    "Re-analyze" button does this).
    """
    from app.settings import get_settings

    result = await session.execute(select(Actor).where(Actor.id == actor_id))
    actor = result.scalar_one_or_none()
    if not actor:
        raise NotFoundError(f"Actor {actor_id} not found")
    if body is None:
        body = AnalyzeRequest()

    # Cache-first: serve the saved row if it has content at the current
    # prompt version. Empty rows (from prior quota failures) are NOT
    # cache-worthy.
    if not body.force:
        existing = await session.get(ActorInsight, actor_id)
        if existing and existing.prompt_version == PROMPT_VERSION:
            ep = existing.payload or {}
            has_hunt = bool((ep.get("hunting_hypothesis") or {}).get("hypothesis"))
            has_iocs = bool(ep.get("iocs_extracted"))
            has_flow = bool((ep.get("attack_flow") or {}).get("output", {}).get("nodes"))
            if has_hunt or has_iocs or has_flow:
                log.info(
                    "actor_analyze_cache_hit actor_id=%s pv=%s hunt=%s iocs=%s flow=%s",
                    actor_id, existing.prompt_version, has_hunt, has_iocs, has_flow,
                )
                return ActorInsightOut.model_validate(existing)

    settings = get_settings()
    jwt = getattr(request.app.state, "service_jwt", "")

    # Build the actor blob the LLM sees. Includes name + aliases + origin +
    # motivation + target sectors + known TTPs (from actor_ttps table) +
    # tools (from actor_tools).
    ttps_rows = (await session.execute(
        select(ActorTTP).where(ActorTTP.actor_id == actor_id)
        .order_by(ActorTTP.technique_id)
    )).scalars().all()
    tools_rows = (await session.execute(
        select(Tool).join(ActorTool, ActorTool.tool_id == Tool.id)
        .where(ActorTool.actor_id == actor_id)
    )).scalars().all()

    parts = [
        f"Name: {actor.name}",
        f"MITRE ID: {actor.mitre_id or '(none — manual entry)'}",
    ]
    if actor.aliases:        parts.append(f"Aliases: {', '.join(actor.aliases)}")
    if actor.origin_country: parts.append(f"Origin: {actor.origin_country}")
    if actor.motivation:     parts.append(f"Motivation: {', '.join(actor.motivation)}")
    if actor.target_sectors: parts.append(f"Target sectors: {', '.join(actor.target_sectors)}")
    if actor.target_countries: parts.append(f"Target countries: {', '.join(actor.target_countries)}")
    if actor.active_since:   parts.append(f"Active since: {actor.active_since}")
    if actor.last_seen:      parts.append(f"Last seen: {actor.last_seen}")
    if actor.description:    parts.append(f"\nDescription:\n{actor.description}")
    if ttps_rows:
        parts.append("\nKnown TTPs (MITRE ATT&CK):")
        for t in ttps_rows[:40]:
            parts.append(f"  - {t.technique_id}  {t.technique_name or ''}".rstrip())
    if tools_rows:
        parts.append("\nTools / malware used:")
        for t in tools_rows[:25]:
            parts.append(f"  - {t.name}{f' ({t.type})' if t.type else ''}")
    actor_text = "\n".join(parts)

    ai = _smart_client(request, body.model)
    log.info("actor_analyze_start actor_id=%s model=%s", actor_id, ai.model)

    async def _run_iocs() -> dict:
        try:
            r = await generate_structured(
                ai,
                system_prompt=IOC_EXTRACTION_PROMPT,
                user_payload={"text": actor_text[:8000]},
                schema=_IocsOut,
                prompt_version=PROMPT_VERSION,
                max_tokens=1500,
            )
            return r.model_dump()
        except (LiteLLMRateLimitError, LiteLLMRequestTooLargeError, LiteLLMError) as exc:
            log.warning("actor_ioc_extraction_failed: %s", exc)
            return {"iocs_extracted": [], "error": str(exc)[:200]}

    async def _run_hunt() -> dict:
        try:
            r = await generate_structured(
                ai,
                system_prompt=HUNTING_PROMPT,
                user_payload={"actor": actor_text[:6000]},
                schema=_HuntingOut,
                prompt_version=PROMPT_VERSION,
                max_tokens=2000,
            )
            return r.model_dump()
        except (LiteLLMRateLimitError, LiteLLMRequestTooLargeError, LiteLLMError) as exc:
            log.warning("actor_hunting_hypothesis_failed: %s", exc)
            return {"hypothesis": "", "wazuh_rule": "",
                    "key_artifacts": [], "mitre_techniques": [], "error": str(exc)[:200]}

    async def _run_flow() -> dict:
        if body.flowviz is False:
            return {}
        # Build a short attack-scenario sentence for flowviz. Actor name +
        # primary motivation + primary sector + lead TTPs.
        flow_seed_parts = [f"{actor.name}"]
        if actor.motivation: flow_seed_parts.append(f"({', '.join(actor.motivation[:2])})")
        if actor.target_sectors: flow_seed_parts.append(f"targeting {', '.join(actor.target_sectors[:2])}")
        if ttps_rows:
            tids = [t.technique_id for t in ttps_rows[:5]]
            flow_seed_parts.append(f"using {', '.join(tids)}")
        flow_input = (" ".join(flow_seed_parts) + ". " + (actor.description or "")).strip()[:800]
        if not flow_input:
            return {}
        try:
            headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}
            async with httpx.AsyncClient(headers=headers, timeout=180) as c:
                r = await c.post(f"{settings.flowviz_url}/flows", json={"input": flow_input})
                if r.status_code == 200:
                    return r.json()
                log.warning("actor_flowviz_returned_%s body=%s", r.status_code, r.text[:200])
                return {"error": f"flowviz {r.status_code}", "detail": r.text[:200]}
        except Exception as exc:
            log.warning("actor_flowviz_call_failed: %s", exc)
            return {"error": str(exc)[:200]}

    # GitHub Models concurrent-request caps differ across models — gpt-4o
    # allows 2, gpt-5-chat allows only 1. Serialize ALL three legs so we
    # never trip "Rate limit of N per 0s for UserConcurrentRequests"
    # regardless of which smart-picker model we landed on. Wall time
    # ~15-30s + flowviz (~80s); analysts hit "Generate" once per actor.
    try:
        iocs_result = await _run_iocs()
        hunt_result = await _run_hunt()
        flow_result = await _run_flow()
    except LiteLLMRateLimitError as exc:
        retry = exc.retry_after_seconds
        detail = f"AI provider is rate-limited (retry in ~{retry}s)." if retry else "AI provider rate-limited."
        headers = {"Retry-After": str(retry)} if retry else None
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail, headers=headers) from exc

    payload = {
        "iocs_extracted": iocs_result.get("iocs_extracted", []),
        "hunting_hypothesis": {k: v for k, v in hunt_result.items() if k != "error"},
        "attack_flow": flow_result,
        "source_blob_excerpt": actor_text[:800],
    }
    if iocs_result.get("error"):
        payload["iocs_extracted_error"] = iocs_result["error"]
    if hunt_result.get("error"):
        payload["hunting_hypothesis_error"] = hunt_result["error"]

    # Auto-promote extracted IOCs into the IOC library so they show up in
    # /iocs (the analyst doesn't have to manually copy them across).
    # Each IOC is keyed by (type, normalized_value) on the receiver side;
    # a 201 means newly created, a duplicate just adds us as a source.
    # Best-effort — failures don't fail the analyze call.
    promoted = 0
    if iocs_ok and jwt:
        try:
            async with httpx.AsyncClient(
                headers={"Authorization": f"Bearer {jwt}"}, timeout=15,
            ) as c_ioc:
                for ioc in iocs_result.get("iocs_extracted", []):
                    ioc_type = ioc.get("type") if isinstance(ioc, dict) else None
                    ioc_val  = ioc.get("value") if isinstance(ioc, dict) else None
                    if not ioc_type or not ioc_val:
                        continue
                    # Strip our hash_* prefixes; IOC library uses bare "sha256" etc.
                    canonical_type = ioc_type.replace("hash_", "") if ioc_type.startswith("hash_") else ioc_type
                    try:
                        resp = await c_ioc.post(
                            f"{settings.ioc_collector_url}/indicators",
                            json={
                                "type": canonical_type,
                                "value": ioc_val,
                                "tags": [f"actor:{actor.name}", "from-actor-insight"],
                                "threat_type": (ioc.get("context") or "")[:120] or None,
                            },
                        )
                        if resp.status_code in (200, 201):
                            promoted += 1
                    except Exception as exc:
                        log.warning("ioc_promote_failed value=%s err=%s", ioc_val, exc)
            payload["iocs_promoted"] = promoted
            log.info("actor_analyze_iocs_promoted actor_id=%s promoted=%d/%d",
                     actor_id, promoted, len(iocs_result.get("iocs_extracted", [])))
        except Exception as exc:
            log.warning("ioc_promote_outer_failed: %s", exc)

    existing = await session.get(ActorInsight, actor_id)
    hunt_ok = bool(hunt_result.get("hypothesis"))
    iocs_ok = bool(iocs_result.get("iocs_extracted"))

    # If both legs failed and we already have a good row, preserve it.
    if existing and not hunt_ok and not iocs_ok:
        log.warning("actor_analyze_preserved_cache actor_id=%s reason=both_legs_failed", actor_id)
        retry_hint = ""
        err_blob = (hunt_result.get("error") or "") + " " + (iocs_result.get("error") or "")
        import re as _re
        m = _re.search(r"wait\s+(\d+)\s+seconds", err_blob)
        if m:
            try:
                retry_hint = f" Retry in ~{int(m.group(1))//60} min."
            except ValueError:
                pass
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"AI provider out of daily quota — cached insight preserved.{retry_hint}",
        )

    now = datetime.now(timezone.utc)
    if existing:
        # Lossless merge: if any leg returned empty but the previous row
        # had content, carry over the old content for that leg.
        old = existing.payload or {}
        old_hunt = old.get("hunting_hypothesis") or {}
        old_iocs = old.get("iocs_extracted") or []
        old_flow = old.get("attack_flow") or {}
        if not hunt_ok and old_hunt.get("hypothesis"):
            payload["hunting_hypothesis"] = old_hunt
            payload["hunting_hypothesis_carried_over"] = True
        if not iocs_ok and old_iocs:
            payload["iocs_extracted"] = old_iocs
            payload["iocs_extracted_carried_over"] = True
        old_nodes = (old_flow.get("output") or {}).get("nodes") or []
        new_nodes = (flow_result.get("output") or {}).get("nodes") or [] if flow_result else []
        if not new_nodes and old_nodes:
            payload["attack_flow"] = old_flow
            payload["attack_flow_carried_over"] = True

        existing.payload = payload
        existing.model_name = ai.model
        existing.prompt_version = PROMPT_VERSION
        existing.generated_at = now
    else:
        existing = ActorInsight(
            actor_id=actor_id,
            payload=payload,
            model_name=ai.model,
            prompt_version=PROMPT_VERSION,
            generated_at=now,
        )
        session.add(existing)
    await session.commit()
    await session.refresh(existing)
    log.info(
        "actor_analyze_done actor_id=%s iocs=%d hypothesis_chars=%d flow_nodes=%d",
        actor_id,
        len(payload["iocs_extracted"]),
        len(payload["hunting_hypothesis"].get("hypothesis", "")),
        len((flow_result.get("output") or {}).get("nodes", []) or []),
    )
    return ActorInsightOut.model_validate(existing)


@router.get(
    "/{actor_id}/ttps",
    response_model=list,
    dependencies=[Depends(require_permission("actors:read"))],
)
async def list_actor_ttps(actor_id: UUID, session: SessionDep):
    result = await session.execute(
        select(ActorTTP).where(ActorTTP.actor_id == actor_id).order_by(ActorTTP.technique_id)
    )
    return result.scalars().all()


@router.get(
    "/{actor_id}/ransomware",
    response_model=list[RansomwareGroupOut],
    dependencies=[Depends(require_permission("actors:read"))],
)
async def list_actor_ransomware(actor_id: UUID, session: SessionDep):
    """Ransomware groups correlated with this MITRE actor."""
    result = await session.execute(
        select(RansomwareGroup)
        .where(RansomwareGroup.actor_id == actor_id)
        .order_by(RansomwareGroup.name)
    )
    return [RansomwareGroupOut.model_validate(g) for g in result.scalars().all()]
