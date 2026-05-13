from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_db import get_session

from app.db import get_session_factory
from app.models import MISPEvent, MISPIoc
from app.schemas import MISPEventOut, MISPIocOut
from app.sources.misp import push_iocs_to_misp, sync_misp

router = APIRouter(prefix="/misp", tags=["misp"])


async def _session_dep():
    # async-generator wrapper: FastAPI iterates exactly once,
    # yielding the live session into the endpoint.
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


@router.get("/events", response_model=list[MISPEventOut], dependencies=[Depends(require_permission("integrations:read"))])
async def list_events(
    session: SessionDep,
    since: datetime | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(MISPEvent)
    if since:
        stmt = stmt.where(MISPEvent.date >= since.date())
    stmt = stmt.order_by(MISPEvent.date.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/events/{event_id}", response_model=MISPEventOut, dependencies=[Depends(require_permission("integrations:read"))])
async def get_event(event_id: str, session: SessionDep):
    from tip_common import NotFoundError

    result = await session.execute(select(MISPEvent).where(MISPEvent.event_id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise NotFoundError(f"MISP event {event_id} not found")
    return event


@router.get("/iocs", response_model=list[MISPIocOut], dependencies=[Depends(require_permission("integrations:read"))])
async def list_iocs(
    session: SessionDep,
    type: str | None = Query(None),
    since: datetime | None = Query(None),
    limit: int = Query(100, le=500),
):
    stmt = select(MISPIoc)
    if type:
        stmt = stmt.where(MISPIoc.type == type)
    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/sync", dependencies=[Depends(require_permission("integrations:write"))])
async def sync(request: Request, background_tasks: BackgroundTasks):
    creds = request.app.state.misp_creds
    session_factory = request.app.state.session_factory
    health = request.app.state.source_health
    background_tasks.add_task(
        _do_misp_sync, session_factory, health, creds["url"], creds["api_key"]
    )
    return {"status": "running"}


@router.post("/push", dependencies=[Depends(require_permission("integrations:write"))])
async def push_iocs(
    request: Request,
    indicator_ids: list[UUID] = Body(..., embed=True),
):
    """Push specific IOCs to MISP (or all high-confidence ones if list is empty)."""
    creds = request.app.state.misp_creds
    settings = request.app.state.settings
    session_factory = request.app.state.session_factory
    health = request.app.state.source_health
    async with session_factory() as session:
        pushed = await push_iocs_to_misp(
            session, health,
            base_url=creds["url"],
            api_key=creds["api_key"],
            misp_event_id=creds.get("push_event_id", ""),
            ioc_collector_url=settings.ioc_collector_url,
        )
    return {"pushed": pushed}


async def _do_misp_sync(session_factory, health, url, api_key):
    async with session_factory() as session:
        await sync_misp(session, health, url, api_key)
