from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_db import get_session

from app.db import get_session_factory
from app.models import ActorTTP, Tool
from app.schemas import ToolOut

router = APIRouter(tags=["tools"])


async def _session_dep():
    # async-generator wrapper: FastAPI iterates exactly once,
    # yielding the live session into the endpoint.
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


@router.get("/tools", response_model=list[ToolOut], dependencies=[Depends(require_permission("actors:read"))])
async def list_tools(
    session: SessionDep,
    type: str | None = Query(None, description="malware or tool"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    q = select(Tool)
    if type:
        q = q.where(Tool.type == type)
    q = q.order_by(Tool.name).offset(offset).limit(limit)
    result = await session.execute(q)
    return result.scalars().all()


@router.get("/tools/{tool_id}", response_model=ToolOut, dependencies=[Depends(require_permission("actors:read"))])
async def get_tool(tool_id: UUID, session: SessionDep):
    from tip_common import NotFoundError

    result = await session.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise NotFoundError(f"Tool {tool_id} not found")
    return tool


@router.get("/ttps/{technique_id}", dependencies=[Depends(require_permission("actors:read"))])
async def actors_using_technique(technique_id: str, session: SessionDep):
    """Returns actors that use the given ATT&CK technique."""
    from app.models import Actor

    result = await session.execute(
        select(Actor)
        .join(ActorTTP, Actor.id == ActorTTP.actor_id)
        .where(ActorTTP.technique_id == technique_id)
        .order_by(Actor.name)
    )
    actors = result.scalars().all()
    return [{"id": str(a.id), "name": a.name, "mitre_id": a.mitre_id, "status": a.status} for a in actors]
