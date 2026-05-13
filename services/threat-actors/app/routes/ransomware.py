from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_db import get_session

from app.db import get_session_factory
from app.models import RansomwareGroup, RansomwareVictim
from app.schemas import RansomwareGroupOut, RansomwareVictimOut

router = APIRouter(prefix="/ransomware", tags=["ransomware"])


async def _session_dep():
    # async-generator wrapper: FastAPI iterates exactly once,
    # yielding the live session into the endpoint.
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


@router.get("/groups", response_model=list[RansomwareGroupOut], dependencies=[Depends(require_permission("actors:read"))])
async def list_groups(
    session: SessionDep,
    status: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    q = select(RansomwareGroup)
    if status:
        q = q.where(RansomwareGroup.status == status)
    q = q.order_by(RansomwareGroup.name).offset(offset).limit(limit)
    result = await session.execute(q)
    return result.scalars().all()


@router.get("/groups/{group_id}", response_model=RansomwareGroupOut, dependencies=[Depends(require_permission("actors:read"))])
async def get_group(group_id: UUID, session: SessionDep):
    from tip_common import NotFoundError

    result = await session.execute(select(RansomwareGroup).where(RansomwareGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise NotFoundError(f"Ransomware group {group_id} not found")
    return group


@router.get("/victims", response_model=list[RansomwareVictimOut], dependencies=[Depends(require_permission("actors:read"))])
async def list_victims(
    session: SessionDep,
    group_id: UUID | None = Query(None),
    since: datetime | None = Query(None),
    country: str | None = Query(None),
    sector: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    q = select(RansomwareVictim)
    if group_id:
        q = q.where(RansomwareVictim.group_id == group_id)
    if since:
        q = q.where(RansomwareVictim.disclosed_at >= since)
    if country:
        q = q.where(RansomwareVictim.country == country)
    if sector:
        q = q.where(RansomwareVictim.sector == sector)
    q = q.order_by(RansomwareVictim.disclosed_at.desc()).offset(offset).limit(limit)
    result = await session.execute(q)
    return result.scalars().all()
