import asyncio
import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_ai import (
    LiteLLMError,
    LiteLLMRateLimitError,
    LiteLLMRequestTooLargeError,
    build_ai_client,
    generate_structured,
)
from tip_auth import require_permission
from tip_common import NotFoundError, resolve_sort
from tip_db import get_session

from app.db import get_session_factory
from app.models import HIBPBreach, Threat, ThreatInsight
from app.prompts import HUNTING_PROMPT, IOC_EXTRACTION_PROMPT, PROMPT_VERSION
from app.schemas import (
    AnalystStatusUpdate,
    AnalyzeRequest,
    HIBPBreachOut,
    InsightOverrideIn,
    ThreatCreateManual,
    ThreatInsightOut,
    ThreatList,
    ThreatOut,
)

log = logging.getLogger(__name__)

router = APIRouter(tags=["threats"])


async def _session_dep():
    # async-generator wrapper: FastAPI iterates exactly once,
    # yielding the live session into the endpoint.
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


_THREAT_SORT_COLS = {
    "observed_at":      Threat.observed_at,
    "title":            Threat.title,
    "severity":         Threat.severity,
    "type":             Threat.type,
    "confidence_score": Threat.confidence_score,
    "analyst_status":   Threat.analyst_status,
}


@router.get(
    "/threats",
    response_model=ThreatList,
    dependencies=[Depends(require_permission("threats:read"))],
)
async def list_threats(
    session: SessionDep,
    type: str | None = Query(None),
    since: datetime | None = Query(None),
    severity: str | None = Query(None),
    q: str | None = Query(None),
    include_not_relevant: bool = Query(False),
    sort_by: str | None = Query(None, description=f"One of: {', '.join(sorted(_THREAT_SORT_COLS))}"),
    sort_dir: str | None = Query(None, description="asc | desc"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(Threat)
    if not include_not_relevant:
        stmt = stmt.where(Threat.analyst_status != "not_relevant")
    if type:
        stmt = stmt.where(Threat.type == type)
    if since:
        stmt = stmt.where(Threat.observed_at >= since)
    if severity:
        stmt = stmt.where(Threat.severity == severity)
    if q:
        stmt = stmt.where(Threat.title.ilike(f"%{q}%"))
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(
        resolve_sort(sort_by, sort_dir, _THREAT_SORT_COLS, default="observed_at")
    ).offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return ThreatList(items=[ThreatOut.model_validate(r) for r in rows], total=total)


@router.get("/threats/{threat_id}", response_model=ThreatOut, dependencies=[Depends(require_permission("threats:read"))])
async def get_threat(threat_id: UUID, session: SessionDep):
    result = await session.execute(select(Threat).where(Threat.id == threat_id))
    threat = result.scalar_one_or_none()
    if not threat:
        raise NotFoundError(f"Threat {threat_id} not found")
    return threat


@router.post("/threats", response_model=ThreatOut, status_code=201, dependencies=[Depends(require_permission("threats:write"))])
async def create_threat_manual(body: ThreatCreateManual, session: SessionDep):
    """Analyst-created threat entry."""
    from tip_auth import current_user
    threat = Threat(
        id=_uuid.uuid4(),
        type=body.type,
        title=body.title,
        source="analyst:manual",
        observed_at=datetime.now(timezone.utc),
        summary=body.summary,
        severity=body.severity,
        details=body.details,
        confidence_score=0.95,
        confidence_inputs={"source_reliability": 0.95, "weights_version": "manual_v1"},
        analyst_status="reviewed",
        manual_source="analyst:manual",
    )
    session.add(threat)
    await session.flush()
    return ThreatOut.model_validate(threat)


@router.patch("/threats/{threat_id}/status", response_model=ThreatOut, dependencies=[Depends(require_permission("threats:write"))])
async def update_threat_status(
    threat_id: UUID,
    body: AnalystStatusUpdate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: SessionDep,
):
    result = await session.execute(select(Threat).where(Threat.id == threat_id))
    threat = result.scalar_one_or_none()
    if not threat:
        raise NotFoundError(f"Threat {threat_id} not found")
    old_status = threat.analyst_status
    threat.analyst_status = body.analyst_status
    await session.flush()

    # When marked 'relevant', auto-add affected products to CMDB
    if body.analyst_status == "relevant" and old_status != "relevant":
        products = _extract_products_from_threat(threat)
        if products:
            from app.settings import get_settings
            settings = get_settings()
            jwt = getattr(request.app.state, "service_jwt", "") or ""
            for product in products:
                background_tasks.add_task(
                    _auto_add_product, settings.cmdb_url, jwt, "threat", str(threat_id), product
                )

    return ThreatOut.model_validate(threat)


def _extract_products_from_threat(threat: Threat) -> list[str]:
    """Extract affected product names from threat details."""
    products: list[str] = []
    details = threat.details or {}
    if isinstance(details, dict):
        for prod in details.get("affected_products", []):
            if isinstance(prod, str) and prod not in products:
                products.append(prod)
    return products[:5]


async def _auto_add_product(
    cmdb_url: str, jwt: str, resource_type: str, resource_id: str, product_name: str
) -> None:
    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=10) as c:
            r = await c.post(
                f"{cmdb_url}/profile/auto-add",
                json={
                    "source_resource_type": resource_type,
                    "source_resource_id": resource_id,
                    "product_name": product_name,
                },
            )
            if r.status_code < 300:
                log.info("Auto-added product '%s' from %s %s", product_name, resource_type, resource_id)
            else:
                log.warning("CMDB auto-add returned %d: %s", r.status_code, r.text[:200])
    except Exception:
        log.exception("Failed to auto-add product '%s' to CMDB", product_name)


@router.get("/threats/{threat_id}/insight", response_model=ThreatInsightOut, dependencies=[Depends(require_permission("threats:read"))])
async def get_threat_insight(threat_id: UUID, session: SessionDep):
    result = await session.execute(
        select(ThreatInsight).where(ThreatInsight.threat_id == threat_id)
    )
    insight = result.scalar_one_or_none()
    if not insight:
        raise NotFoundError(f"No insight for threat {threat_id}")
    return insight


@router.put("/threats/{threat_id}/insight/override", response_model=ThreatInsightOut, dependencies=[Depends(require_permission("threats:write"))])
async def override_threat_insight(threat_id: UUID, body: InsightOverrideIn, session: SessionDep):
    result = await session.execute(
        select(ThreatInsight).where(ThreatInsight.threat_id == threat_id)
    )
    insight = result.scalar_one_or_none()
    if not insight:
        raise NotFoundError(f"No insight for threat {threat_id}")
    insight.analyst_override = body.analyst_override
    await session.flush()
    return ThreatInsightOut.model_validate(insight)


# ── Threat insight v2 ────────────────────────────────────────────────────────
#
# The CLI / orchestrator action queue used to dispatch `extract_iocs` and
# `map_ttps` for a threat; results landed in `orchestrator.action_runs` but
# never made it back to threat_insights, so the analyst saw nothing on the
# detail page. This route now does the whole synthesis inline and persists
# directly, matching the CVE analyze flow:
#
#   1. extract_iocs       (LLM pass — defangs + dedupes)
#   2. hunting_hypothesis (LLM pass — Splunk SPL + Wazuh rule + artifacts)
#   3. attack_flow        (HTTP -> flowviz service, returns nodes+edges)
#
# The model defaults to the "smart" tier (gpt-4o class) instead of the
# minute-budget gpt-4o-mini we use for the brief — IOC extraction + hunt
# rules benefit a lot from a larger context window and stronger reasoning.

_SMART_MODEL_DEFAULTS = [
    # gpt-4.1 first: GitHub Models gives it the largest daily quota
    # (50/day at our PAT tier). gpt-5-chat is capped at 12/day which
    # exhausts after ~4 analyses — analysts hit the 429 wall and
    # generation silently stops. gpt-4o is the last-resort fallback.
    # gpt-5-chat sits between as the "smartest when available" option;
    # the smart picker walks the list in order, so once gpt-4.1's quota
    # is spent we naturally try gpt-5-chat / gpt-4o.
    "github/gpt-4.1",
    "github/gpt-5-chat",
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
    # NOTE: splunk_query removed in PROMPT_VERSION v2 (operator runs Wazuh
    # only — SPL was extra noise). Existing v1 rows still have the field
    # in their JSON payload; the frontend just doesn't render it.
    hypothesis: str
    wazuh_rule: str = ""
    key_artifacts: list[_KeyArtifact] = []
    mitre_techniques: list[str] = []


def _smart_client(request: Request, override_model: str | None):
    """Build an ad-hoc AI client for the smart-tier model.

    Threat insights need richer outputs (~2k tokens of structured JSON for
    Splunk + Wazuh + 5 artifacts + 4 TTPs). gpt-4o-mini's 8K request cap
    chokes on that. We allow the caller to pin a specific model via
    `body.model`; otherwise we walk through `_SMART_MODEL_DEFAULTS` and pick
    the first one whose required key is present in the secrets vault.
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

    # Build a settings copy with our chosen primary so build_ai_client picks it up.
    smart_settings = copy(settings)
    smart_settings.ai_primary_model = chosen or settings.ai_primary_model
    return build_ai_client(secrets, smart_settings)


@router.post(
    "/threats/{threat_id}/analyze",
    response_model=ThreatInsightOut,
    dependencies=[Depends(require_permission("threats:write"))],
)
async def analyze_threat(
    threat_id: UUID,
    request: Request,
    body: AnalyzeRequest | None = None,
    session: SessionDep = None,  # type: ignore[assignment]
) -> ThreatInsightOut:
    """Generate a hunter-ready insight for a threat.

    Synchronous because users hit "Generate insight" and expect the result
    in the same modal — three LLM/HTTP calls in parallel keeps total wall
    time under ~20s on gpt-4o. Persists to `threat_insights` so the panel
    reuses the same data on next page load (no re-billing the LLM).
    """
    from app.settings import get_settings

    result = await session.execute(select(Threat).where(Threat.id == threat_id))
    threat = result.scalar_one_or_none()
    if not threat:
        raise NotFoundError(f"Threat {threat_id} not found")
    if body is None:
        body = AnalyzeRequest()

    # Cache-first: serve the saved insight without re-running the AI when
    # the row already exists at the current prompt version AND has real
    # content. Empty rows (from a prior quota failure) are NOT cache-worthy
    # — we re-run them to backfill. The "Re-analyze" button passes
    # force=true to bypass even good rows. This is what saves analysts
    # from accidentally burning AI quota by clicking through threats
    # they've already triaged.
    if not body.force:
        existing = await session.get(ThreatInsight, threat_id)
        if existing and existing.prompt_version == PROMPT_VERSION:
            ep = existing.payload or {}
            has_hunt = bool((ep.get("hunting_hypothesis") or {}).get("hypothesis"))
            has_iocs = bool(ep.get("iocs_extracted"))
            has_flow = bool((ep.get("attack_flow") or {}).get("output", {}).get("nodes"))
            if has_hunt or has_iocs or has_flow:
                log.info(
                    "threat_analyze_cache_hit threat_id=%s prompt_version=%s "
                    "hunt=%s iocs=%s flow=%s",
                    threat_id, existing.prompt_version, has_hunt, has_iocs, has_flow,
                )
                return ThreatInsightOut.model_validate(existing)
            log.info(
                "threat_analyze_cache_miss threat_id=%s reason=empty_payload",
                threat_id,
            )

    settings = get_settings()
    jwt = getattr(request.app.state, "service_jwt", "")

    # Build the source blob the LLM sees. We include title + severity +
    # summary + the raw `details` JSON (capped) because supply-chain advisories
    # tend to put IOCs inside details.affected_versions / details.iocs etc.
    import json as _json
    blob_parts = [
        f"Title: {threat.title}",
        f"Type: {threat.type}",
        f"Severity: {threat.severity}",
        f"Source: {threat.source}",
    ]
    if threat.source_url:
        blob_parts.append(f"Source URL: {threat.source_url}")
    if threat.summary:
        blob_parts.append(f"\nSummary:\n{threat.summary}")
    if threat.details:
        try:
            details_json = _json.dumps(threat.details, default=str, indent=2)
        except Exception:
            details_json = str(threat.details)
        blob_parts.append(f"\nStructured details:\n{details_json[:4000]}")
    threat_text = "\n".join(blob_parts)

    ai = _smart_client(request, body.model)
    log.info("threat_analyze_start threat_id=%s model=%s", threat_id, ai.model)

    async def _run_iocs() -> dict:
        try:
            r = await generate_structured(
                ai,
                system_prompt=IOC_EXTRACTION_PROMPT,
                user_payload={"text": threat_text[:8000]},
                schema=_IocsOut,
                prompt_version=PROMPT_VERSION,
                max_tokens=1500,
            )
            return r.model_dump()
        except (LiteLLMRateLimitError, LiteLLMRequestTooLargeError, LiteLLMError) as exc:
            log.warning("ioc_extraction_failed: %s", exc)
            return {"iocs_extracted": [], "error": str(exc)[:200]}

    async def _run_hunt() -> dict:
        try:
            r = await generate_structured(
                ai,
                system_prompt=HUNTING_PROMPT,
                user_payload={"threat": threat_text[:6000]},
                schema=_HuntingOut,
                prompt_version=PROMPT_VERSION,
                max_tokens=2000,
            )
            return r.model_dump()
        except (LiteLLMRateLimitError, LiteLLMRequestTooLargeError, LiteLLMError) as exc:
            log.warning("hunting_hypothesis_failed: %s", exc)
            return {"hypothesis": "", "wazuh_rule": "",
                    "key_artifacts": [], "mitre_techniques": [], "error": str(exc)[:200]}

    async def _run_flow() -> dict:
        if body.flowviz is False:
            return {}
        # Flowviz needs a short, concrete attack-scenario sentence — not the
        # full threat blob — or it produces vague flows.
        flow_input = (threat.summary or threat.title or "").strip()[:800]
        if not flow_input:
            return {}
        try:
            headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}
            # No `model` override — flowviz is opinionated about its own
            # model choice (Sonnet 4.5 / gpt-4.1). The flowviz cache will
            # hit on the second analyze for the same input, so re-running
            # the threat insight doesn't re-bill the attack flow.
            #
            # 180s timeout: gpt-4.1 generating a structured attack flow with
            # 6-12 nodes + edges + technique IDs commonly takes 60-90s. Plus
            # we send the threat blob — the model is doing real work.
            flow_body = {"input": flow_input}
            async with httpx.AsyncClient(headers=headers, timeout=180) as c:
                r = await c.post(f"{settings.flowviz_url}/flows", json=flow_body)
                if r.status_code == 200:
                    return r.json()
                log.warning("flowviz_returned_%s body=%s", r.status_code, r.text[:200])
                return {"error": f"flowviz {r.status_code}", "detail": r.text[:200]}
        except Exception as exc:
            log.warning("flowviz_call_failed: %s", exc)
            return {"error": str(exc)[:200]}

    # Serialize all three legs — GitHub Models concurrent caps vary by model
    # (gpt-4o=2, gpt-5-chat=1). Running them sequentially never trips the
    # limit regardless of which smart-tier model the picker landed on.
    # Wall time ~15-30s for hunt+IOC + flowviz (~80s on its own thread).
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
        "source_blob_excerpt": threat_text[:800],  # for re-runs / debugging
    }
    if iocs_result.get("error"):
        payload["iocs_extracted_error"] = iocs_result["error"]
    if hunt_result.get("error"):
        payload["hunting_hypothesis_error"] = hunt_result["error"]

    # Auto-promote extracted IOCs into the IOC library so they appear in
    # /iocs alongside threat-fox / OTX feeds. Best-effort; failures don't
    # block the analyze. ioc-collector handles dedup (type, normalized_value)
    # and just adds us as a new source for any indicator that already exists.
    iocs_ok = bool(iocs_result.get("iocs_extracted"))
    if iocs_ok and jwt:
        promoted = 0
        try:
            async with httpx.AsyncClient(
                headers={"Authorization": f"Bearer {jwt}"}, timeout=15,
            ) as c_ioc:
                for ioc in iocs_result.get("iocs_extracted", []):
                    ioc_type = ioc.get("type") if isinstance(ioc, dict) else None
                    ioc_val  = ioc.get("value") if isinstance(ioc, dict) else None
                    if not ioc_type or not ioc_val:
                        continue
                    canonical_type = ioc_type.replace("hash_", "") if ioc_type.startswith("hash_") else ioc_type
                    try:
                        resp = await c_ioc.post(
                            f"{settings.ioc_collector_url}/indicators",
                            json={
                                "type": canonical_type,
                                "value": ioc_val,
                                "tags": [f"threat:{threat.type}", "from-threat-insight"],
                                "threat_type": (ioc.get("context") or "")[:120] or None,
                            },
                        )
                        if resp.status_code in (200, 201):
                            promoted += 1
                    except Exception as exc:
                        log.warning("ioc_promote_failed value=%s err=%s", ioc_val, exc)
            payload["iocs_promoted"] = promoted
            log.info("threat_analyze_iocs_promoted threat_id=%s promoted=%d/%d",
                     threat_id, promoted, len(iocs_result.get("iocs_extracted", [])))
        except Exception as exc:
            log.warning("ioc_promote_outer_failed: %s", exc)

    existing = await session.get(ThreatInsight, threat_id)

    # If this fresh run had hunt + IOCs both fail (e.g. daily quota hit) and
    # we already had a good cached row, keep the cached row instead of
    # overwriting it with empty errors. The analyst sees the older real
    # data instead of nothing; the 429 returns to the caller so the UI
    # can surface a "try again later" toast.
    hunt_ok = bool(hunt_result.get("hypothesis"))
    iocs_ok = bool(iocs_result.get("iocs_extracted"))
    if existing and not hunt_ok and not iocs_ok:
        log.warning(
            "threat_analyze_preserved_cache threat_id=%s reason=both_legs_failed "
            "ioc_err=%r hunt_err=%r",
            threat_id, iocs_result.get("error"), hunt_result.get("error"),
        )
        retry_hint = ""
        # Best-effort retry-after parse from the error string
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

    # Upsert into threat_insights — but only overwrite a good cached row
    # when the new payload is at least as complete (i.e. not a downgrade).
    now = datetime.now(timezone.utc)
    if existing:
        # If new run is partial AND old was complete, merge: keep old hunt
        # / flow if new ones are empty. Same for IOCs. Lossless re-analyze.
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
        existing = ThreatInsight(
            threat_id=threat_id,
            payload=payload,
            model_name=ai.model,
            prompt_version=PROMPT_VERSION,
            generated_at=now,
        )
        session.add(existing)
    await session.commit()
    await session.refresh(existing)
    log.info("threat_analyze_done threat_id=%s iocs=%d hypothesis_chars=%d flow_nodes=%d",
             threat_id,
             len(payload["iocs_extracted"]),
             len(payload["hunting_hypothesis"].get("hypothesis", "")),
             len((flow_result.get("output") or {}).get("nodes", []) or []))
    return ThreatInsightOut.model_validate(existing)


@router.get("/hibp-breaches", response_model=list[HIBPBreachOut], dependencies=[Depends(require_permission("threats:read"))])
async def list_breaches(
    session: SessionDep,
    is_verified: bool | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(HIBPBreach)
    if is_verified is not None:
        stmt = stmt.where(HIBPBreach.is_verified == is_verified)
    stmt = stmt.order_by(HIBPBreach.added_date.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()
