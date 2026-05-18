from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_common import NotFoundError
from tip_db import get_session

from app.db import get_session_factory
from app.models import Actor, RansomwareGroup, RansomwareVictim
from app.schemas import (
    ActorOut,
    RansomwareGroupList,
    RansomwareGroupOut,
    RansomwareVictimList,
    RansomwareVictimOut,
)

router = APIRouter(prefix="/ransomware", tags=["ransomware"])


async def _session_dep():
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


@router.get(
    "/groups",
    response_model=RansomwareGroupList,
    dependencies=[Depends(require_permission("actors:read"))],
)
async def list_groups(
    session: SessionDep,
    q: str | None = Query(None, description="Search across name + aliases + description"),
    status: str | None = Query(None),
    country: str | None = Query(None, description="Match in target_countries"),
    sector: str | None = Query(None, description="Match in target_sectors"),
    actor_id: UUID | None = Query(None, description="Only groups correlated to this actor"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    stmt = select(RansomwareGroup)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                RansomwareGroup.name.ilike(like),
                RansomwareGroup.description.ilike(like),
                func.array_to_string(RansomwareGroup.aliases, ",").ilike(like),
            )
        )
    if status:
        stmt = stmt.where(RansomwareGroup.status == status)
    if country:
        stmt = stmt.where(RansomwareGroup.target_countries.any(country))
    if sector:
        stmt = stmt.where(RansomwareGroup.target_sectors.any(sector))
    if actor_id is not None:
        stmt = stmt.where(RansomwareGroup.actor_id == actor_id)

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(RansomwareGroup.victim_count.desc(), RansomwareGroup.name).offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return RansomwareGroupList(items=[RansomwareGroupOut.model_validate(r) for r in rows], total=total)


@router.get(
    "/groups/{group_id}",
    response_model=RansomwareGroupOut,
    dependencies=[Depends(require_permission("actors:read"))],
)
async def get_group(group_id: UUID, session: SessionDep):
    result = await session.execute(select(RansomwareGroup).where(RansomwareGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise NotFoundError(f"Ransomware group {group_id} not found")
    return group


@router.get(
    "/groups/{group_id}/actor",
    response_model=ActorOut | None,
    dependencies=[Depends(require_permission("actors:read"))],
)
async def get_group_actor(group_id: UUID, session: SessionDep):
    """The MITRE intrusion-set linked to this ransomware group, if any."""
    group = (await session.execute(select(RansomwareGroup).where(RansomwareGroup.id == group_id))).scalar_one_or_none()
    if not group:
        raise NotFoundError(f"Ransomware group {group_id} not found")
    if not group.actor_id:
        return None
    actor = (await session.execute(select(Actor).where(Actor.id == group.actor_id))).scalar_one_or_none()
    if not actor:
        return None
    return ActorOut.model_validate(actor)


@router.get(
    "/groups/{group_id}/victims",
    response_model=RansomwareVictimList,
    dependencies=[Depends(require_permission("actors:read"))],
)
async def list_group_victims(
    group_id: UUID,
    session: SessionDep,
    since: datetime | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    stmt = select(RansomwareVictim).where(RansomwareVictim.group_id == group_id)
    if since:
        stmt = stmt.where(RansomwareVictim.disclosed_at >= since)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(RansomwareVictim.disclosed_at.desc().nulls_last()).offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()

    # Pull group + actor info once (all victims share the group)
    group = (await session.execute(select(RansomwareGroup).where(RansomwareGroup.id == group_id))).scalar_one_or_none()
    actor_name: str | None = None
    actor_id_val = group.actor_id if group else None
    if actor_id_val:
        actor = (await session.execute(select(Actor).where(Actor.id == actor_id_val))).scalar_one_or_none()
        actor_name = actor.name if actor else None
    group_name = group.name if group else None

    items = []
    for r in rows:
        out = RansomwareVictimOut.model_validate(r)
        out.group_name = group_name
        out.actor_id = actor_id_val
        out.actor_name = actor_name
        items.append(out)
    return RansomwareVictimList(items=items, total=total)


@router.get(
    "/victims",
    response_model=RansomwareVictimList,
    dependencies=[Depends(require_permission("actors:read"))],
)
async def list_victims(
    session: SessionDep,
    q: str | None = Query(None, description="Substring match on victim_name + sector + country"),
    group_id: UUID | None = Query(None),
    actor_id: UUID | None = Query(None, description="Only victims of groups correlated to this actor"),
    since: datetime | None = Query(None),
    country: str | None = Query(None),
    sector: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    # Join group so we can return group_name + actor_id without N+1 queries
    stmt = (
        select(
            RansomwareVictim,
            RansomwareGroup.name.label("group_name"),
            RansomwareGroup.actor_id.label("group_actor_id"),
        )
        .join(RansomwareGroup, RansomwareVictim.group_id == RansomwareGroup.id)
    )
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                RansomwareVictim.victim_name.ilike(like),
                RansomwareVictim.country.ilike(like),
                RansomwareVictim.sector.ilike(like),
            )
        )
    if group_id:
        stmt = stmt.where(RansomwareVictim.group_id == group_id)
    if actor_id is not None:
        stmt = stmt.where(RansomwareGroup.actor_id == actor_id)
    if since:
        stmt = stmt.where(RansomwareVictim.disclosed_at >= since)
    if country:
        stmt = stmt.where(RansomwareVictim.country == country)
    if sector:
        stmt = stmt.where(RansomwareVictim.sector == sector)

    # Count rows in subquery (use only the victim id column to keep it simple)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(RansomwareVictim.disclosed_at.desc().nulls_last()).offset(offset).limit(limit)
    rows = (await session.execute(stmt)).all()

    # Resolve actor names in one pass (small number of distinct actors)
    actor_ids = {r.group_actor_id for r in rows if r.group_actor_id}
    actor_name_by_id: dict = {}
    if actor_ids:
        for a in (await session.execute(select(Actor).where(Actor.id.in_(actor_ids)))).scalars().all():
            actor_name_by_id[a.id] = a.name

    items = []
    for r in rows:
        victim = r.RansomwareVictim
        out = RansomwareVictimOut.model_validate(victim)
        out.group_name = r.group_name
        out.actor_id = r.group_actor_id
        out.actor_name = actor_name_by_id.get(r.group_actor_id) if r.group_actor_id else None
        items.append(out)
    return RansomwareVictimList(items=items, total=total)


@router.get(
    "/victims/{victim_id}",
    response_model=RansomwareVictimOut,
    dependencies=[Depends(require_permission("actors:read"))],
)
async def get_victim(victim_id: UUID, session: SessionDep):
    victim = (await session.execute(select(RansomwareVictim).where(RansomwareVictim.id == victim_id))).scalar_one_or_none()
    if not victim:
        raise NotFoundError(f"Victim {victim_id} not found")
    group = (await session.execute(select(RansomwareGroup).where(RansomwareGroup.id == victim.group_id))).scalar_one_or_none()
    out = RansomwareVictimOut.model_validate(victim)
    if group:
        out.group_name = group.name
        out.actor_id = group.actor_id
        if group.actor_id:
            actor = (await session.execute(select(Actor).where(Actor.id == group.actor_id))).scalar_one_or_none()
            if actor:
                out.actor_name = actor.name
    return out
