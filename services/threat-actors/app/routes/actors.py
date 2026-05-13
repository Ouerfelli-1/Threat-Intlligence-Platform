from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import current_user, require_permission
from tip_db import get_session

from app.db import get_session_factory
from app.models import Actor, ActorInsight, ActorTool, ActorTTP, Tool
from app.schemas import ActorDetailOut, ActorInsightOut, ActorOut

router = APIRouter(prefix="/actors", tags=["actors"])


async def _session_dep():
    # async-generator wrapper: FastAPI iterates exactly once,
    # yielding the live session into the endpoint.
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


@router.get("", response_model=list[ActorOut], dependencies=[Depends(require_permission("actors:read"))])
async def list_actors(
    session: SessionDep,
    sector: str | None = Query(None),
    country: str | None = Query(None),
    motivation: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    q = select(Actor)
    if sector:
        q = q.where(Actor.target_sectors.any(sector))
    if country:
        q = q.where(Actor.target_countries.any(country))
    if motivation:
        q = q.where(Actor.motivation.any(motivation))
    if status:
        q = q.where(Actor.status == status)
    q = q.order_by(Actor.name).offset(offset).limit(limit)
    result = await session.execute(q)
    return result.scalars().all()


@router.get("/{actor_id}", response_model=ActorDetailOut, dependencies=[Depends(require_permission("actors:read"))])
async def get_actor(actor_id: UUID, session: SessionDep):
    from tip_common import NotFoundError

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

    return ActorDetailOut(
        **ActorOut.model_validate(actor).model_dump(),
        ttps=ttps_result.scalars().all(),
        tools=tools_result.scalars().all(),
    )


@router.get("/{actor_id}/insight", response_model=ActorInsightOut, dependencies=[Depends(require_permission("actors:read"))])
async def get_actor_insight(actor_id: UUID, session: SessionDep):
    from tip_common import NotFoundError

    result = await session.execute(
        select(ActorInsight).where(ActorInsight.actor_id == actor_id)
    )
    insight = result.scalar_one_or_none()
    if not insight:
        raise NotFoundError(f"No insight for actor {actor_id}")
    return insight


@router.get("/{actor_id}/ttps", response_model=list, dependencies=[Depends(require_permission("actors:read"))])
async def list_actor_ttps(actor_id: UUID, session: SessionDep):
    result = await session.execute(
        select(ActorTTP).where(ActorTTP.actor_id == actor_id).order_by(ActorTTP.technique_id)
    )
    return result.scalars().all()
