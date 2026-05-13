from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_db import get_session

from app.db import get_session_factory
from app.models import HIBPBreach, Threat, ThreatInsight
from app.schemas import HIBPBreachOut, ThreatInsightOut, ThreatOut

router = APIRouter(tags=["threats"])


async def _session_dep():
    # async-generator wrapper: FastAPI iterates exactly once,
    # yielding the live session into the endpoint.
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


@router.get("/threats", response_model=list[ThreatOut], dependencies=[Depends(require_permission("threats:read"))])
async def list_threats(
    session: SessionDep,
    type: str | None = Query(None),
    since: datetime | None = Query(None),
    severity: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(Threat)
    if type:
        stmt = stmt.where(Threat.type == type)
    if since:
        stmt = stmt.where(Threat.observed_at >= since)
    if severity:
        stmt = stmt.where(Threat.severity == severity)
    if q:
        stmt = stmt.where(Threat.title.ilike(f"%{q}%"))
    stmt = stmt.order_by(Threat.observed_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/threats/{threat_id}", response_model=ThreatOut, dependencies=[Depends(require_permission("threats:read"))])
async def get_threat(threat_id: UUID, session: SessionDep):
    from tip_common import NotFoundError

    result = await session.execute(select(Threat).where(Threat.id == threat_id))
    threat = result.scalar_one_or_none()
    if not threat:
        raise NotFoundError(f"Threat {threat_id} not found")
    return threat


@router.get("/threats/{threat_id}/insight", response_model=ThreatInsightOut, dependencies=[Depends(require_permission("threats:read"))])
async def get_threat_insight(threat_id: UUID, session: SessionDep):
    from tip_common import NotFoundError

    result = await session.execute(
        select(ThreatInsight).where(ThreatInsight.threat_id == threat_id)
    )
    insight = result.scalar_one_or_none()
    if not insight:
        raise NotFoundError(f"No insight for threat {threat_id}")
    return insight


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
