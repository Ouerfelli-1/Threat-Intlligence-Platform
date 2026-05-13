import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_cache import Cache
from tip_common import NotFoundError
from tip_schemas import normalize_indicator

from app.db import get_session
from app.models import Indicator, IndicatorSource
from app.schemas import (
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


@router.get(
    "",
    response_model=IndicatorList,
    dependencies=[Depends(require_permission("iocs:read"))],
)
async def list_indicators(
    type: str | None = None,
    value: str | None = None,
    since: str | None = None,
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> IndicatorList:
    stmt = select(Indicator)
    if type:
        stmt = stmt.where(Indicator.type == type)
    if value:
        try:
            norm = normalize_indicator(type or "domain", value)
            stmt = stmt.where(Indicator.normalized_value == norm)
        except ValueError:
            stmt = stmt.where(Indicator.raw_value.ilike(f"%{value}%"))
    if min_confidence > 0:
        stmt = stmt.where(Indicator.confidence_score >= min_confidence)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Indicator.last_seen.desc()).limit(limit).offset(offset)
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
