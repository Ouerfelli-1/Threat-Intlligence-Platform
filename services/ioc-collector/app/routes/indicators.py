import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import current_user, require_permission, AuthContext
from tip_cache import Cache
from tip_common import NotFoundError, resolve_sort
from tip_schemas import normalize_indicator
from tip_schemas.confidence import DataType, ConfidenceInputs, compute_confidence

from app.db import get_session
from app.models import Indicator, IndicatorSource
from app.schemas import (
    AnalystStatusUpdate,
    AnalyzeRequest,
    IndicatorCreateManual,
    IndicatorList,
    IndicatorOut,
    IndicatorWithSources,
    LookupHit,
    LookupRequest,
    LookupResponse,
)

router = APIRouter(prefix="/indicators", tags=["indicators"])

CACHE_TTL = 600


def _cache_key(typ: str, val: str) -> str:
    return f"ioc:{typ}:{val}"


_IOC_SORT_COLS = {
    "last_seen":        Indicator.last_seen,
    "first_seen":       Indicator.first_seen,
    "confidence_score": Indicator.confidence_score,
    "type":             Indicator.type,
    "normalized_value": Indicator.normalized_value,
    "analyst_status":   Indicator.analyst_status,
}


@router.get(
    "",
    response_model=IndicatorList,
    dependencies=[Depends(require_permission("iocs:read"))],
)
async def list_indicators(
    type: str | None = None,
    value: str | None = None,
    q: str | None = None,
    since: str | None = None,
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    include_not_relevant: bool = Query(False),
    sort_by: str | None = Query(None, description=f"One of: {', '.join(sorted(_IOC_SORT_COLS))}"),
    sort_dir: str | None = Query(None, description="asc | desc"),
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> IndicatorList:
    stmt = select(Indicator)
    if not include_not_relevant:
        stmt = stmt.where(Indicator.analyst_status != "not_relevant")
    if type:
        stmt = stmt.where(Indicator.type == type)
    if q:
        stmt = stmt.where(
            or_(
                Indicator.normalized_value.ilike(f"%{q}%"),
                Indicator.raw_value.ilike(f"%{q}%"),
                func.array_to_string(Indicator.tags, ",").ilike(f"%{q}%"),
            )
        )
    if value:
        try:
            norm = normalize_indicator(type or "domain", value)
            stmt = stmt.where(Indicator.normalized_value == norm)
        except ValueError:
            stmt = stmt.where(Indicator.raw_value.ilike(f"%{value}%"))
    if min_confidence > 0:
        stmt = stmt.where(Indicator.confidence_score >= min_confidence)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(
        resolve_sort(sort_by, sort_dir, _IOC_SORT_COLS, default="last_seen")
    ).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return IndicatorList(items=[IndicatorOut.model_validate(r) for r in rows], total=total)


@router.get(
    "/{indicator_id}",
    response_model=IndicatorWithSources,
    dependencies=[Depends(require_permission("iocs:read"))],
)
async def get_indicator(
    indicator_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> IndicatorWithSources:
    indicator = await session.get(Indicator, indicator_id)
    if indicator is None:
        raise NotFoundError(f"indicator {indicator_id} not found")
    sources = (
        await session.execute(
            select(IndicatorSource).where(IndicatorSource.indicator_id == indicator.id)
        )
    ).scalars().all()
    out = IndicatorWithSources.model_validate(indicator)
    out.sources = [
        {
            "source_name": s.source_name,
            "source_id": s.source_id,
            "first_reported_at": s.first_reported_at,
            "last_reported_at": s.last_reported_at,
            "malware_family": s.malware_family,
            "threat_type": s.threat_type,
        }
        for s in sources
    ]
    return out


@router.post(
    "/lookup",
    response_model=LookupResponse,
    dependencies=[Depends(require_permission("iocs:read"))],
)
async def lookup(
    request: Request,
    body: LookupRequest,
    session: AsyncSession = Depends(get_session),
) -> LookupResponse:
    cache: Cache = request.app.state.cache
    hits: list[LookupHit] = []
    for item in body.indicators[:200]:
        typ = item.get("type", "")
        val = item.get("value", "")
        try:
            norm = normalize_indicator(typ, val)
        except ValueError:
            hits.append(LookupHit(type=typ, value=val, normalized_value=val, found=False))
            continue
        cached = await cache.get_json(_cache_key(typ, norm))
        if cached is not None:
            hits.append(LookupHit(**cached))
            continue
        row = await session.scalar(
            select(Indicator).where(
                Indicator.type == typ, Indicator.normalized_value == norm
            )
        )
        if row is None:
            hit = LookupHit(type=typ, value=val, normalized_value=norm, found=False)
        else:
            hit = LookupHit(
                type=typ,
                value=val,
                normalized_value=norm,
                found=True,
                indicator=IndicatorOut.model_validate(row),
            )
        await cache.set_json(_cache_key(typ, norm), hit.model_dump(mode="json"), ttl_seconds=CACHE_TTL)
        hits.append(hit)
    return LookupResponse(hits=hits)


@router.post(
    "",
    response_model=IndicatorOut,
    status_code=201,
    dependencies=[Depends(require_permission("iocs:write"))],
)
async def create_indicator_manual(
    body: IndicatorCreateManual,
    ctx: AuthContext = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> IndicatorOut:
    """Analyst-created IOC entry with high reliability."""
    norm = normalize_indicator(body.type, body.value)
    # Check for existing
    existing = await session.scalar(
        select(Indicator).where(
            Indicator.type == body.type, Indicator.normalized_value == norm
        )
    )
    if existing is not None:
        # Add analyst as a source if not already
        src_exists = await session.scalar(
            select(IndicatorSource).where(
                IndicatorSource.indicator_id == existing.id,
                IndicatorSource.source_name == f"analyst:{ctx.subject}",
            )
        )
        if not src_exists:
            now = datetime.now(timezone.utc)
            session.add(IndicatorSource(
                indicator_id=existing.id,
                source_name=f"analyst:{ctx.subject}",
                first_reported_at=now,
                last_reported_at=now,
                malware_family=body.malware_family,
                threat_type=body.threat_type,
            ))
        if body.tags:
            existing.tags = list(set(existing.tags or []) | set(body.tags))
        existing.analyst_status = "reviewed"
        await session.flush()
        return IndicatorOut.model_validate(existing)

    # Create new indicator
    now = datetime.now(timezone.utc)
    inputs = ConfidenceInputs(
        source_reliability=0.95,
        corroboration_count=1,
        days_since_seen=0.0,
        extraction_quality=1.0,
    )
    score = compute_confidence(DataType.IOC, inputs)
    indicator = Indicator(
        id=uuid.uuid4(),
        type=body.type,
        normalized_value=norm,
        raw_value=body.value,
        first_seen=now,
        last_seen=now,
        tags=body.tags or [],
        confidence_score=score,
        confidence_inputs=inputs.model_dump(),
        analyst_status="reviewed",
    )
    session.add(indicator)
    await session.flush()

    session.add(IndicatorSource(
        indicator_id=indicator.id,
        source_name=f"analyst:{ctx.subject}",
        first_reported_at=now,
        last_reported_at=now,
        malware_family=body.malware_family,
        threat_type=body.threat_type,
    ))
    await session.flush()
    return IndicatorOut.model_validate(indicator)


@router.patch(
    "/{indicator_id}/status",
    response_model=IndicatorOut,
    dependencies=[Depends(require_permission("iocs:write"))],
)
async def update_indicator_status(
    indicator_id: uuid.UUID,
    body: AnalystStatusUpdate,
    session: AsyncSession = Depends(get_session),
) -> IndicatorOut:
    indicator = await session.get(Indicator, indicator_id)
    if indicator is None:
        raise NotFoundError(f"indicator {indicator_id} not found")
    indicator.analyst_status = body.analyst_status
    await session.flush()
    return IndicatorOut.model_validate(indicator)


@router.post(
    "/{indicator_id}/analyze",
    status_code=202,
    dependencies=[Depends(require_permission("iocs:write"))],
)
async def analyze_indicator(
    indicator_id: uuid.UUID,
    request: Request,
    body: AnalyzeRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Trigger on-demand AI analysis on this indicator via the orchestrator."""
    from app.settings import get_settings

    indicator = await session.get(Indicator, indicator_id)
    if indicator is None:
        raise NotFoundError(f"indicator {indicator_id} not found")
    if body is None:
        body = AnalyzeRequest()

    settings = get_settings()
    jwt = getattr(request.app.state, "service_jwt", "")
    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}

    actions = body.actions or ["extract_iocs", "map_ttps"]
    if body.flowviz:
        actions = list(set(actions) | {"flowviz"})

    async with httpx.AsyncClient(headers=headers, timeout=30) as c:
        r = await c.post(
            f"{settings.orchestrator_url}/actions/run",
            json={
                "resource_type": "ioc",
                "resource_id": str(indicator_id),
                "actions": actions,
            },
        )
        return r.json()
