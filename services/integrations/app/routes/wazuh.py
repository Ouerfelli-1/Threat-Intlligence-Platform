from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_db import get_session

from app.db import get_session_factory
from app.models import WazuhAgent, WazuhAlert
from app.schemas import WazuhAgentOut, WazuhAlertOut
from app.sources.wazuh import sync_wazuh

router = APIRouter(prefix="/wazuh", tags=["wazuh"])


async def _session_dep():
    # async-generator wrapper: FastAPI iterates exactly once,
    # yielding the live session into the endpoint.
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


@router.get("/alerts", response_model=list[WazuhAlertOut], dependencies=[Depends(require_permission("integrations:read"))])
async def list_alerts(
    session: SessionDep,
    severity_gte: int | None = Query(None),
    agent_id: str | None = Query(None),
    since: datetime | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    stmt = select(WazuhAlert)
    if severity_gte is not None:
        stmt = stmt.where(WazuhAlert.severity >= severity_gte)
    if agent_id:
        stmt = stmt.where(WazuhAlert.agent_id == agent_id)
    if since:
        stmt = stmt.where(WazuhAlert.timestamp >= since)
    stmt = stmt.order_by(WazuhAlert.timestamp.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/agents", response_model=list[WazuhAgentOut], dependencies=[Depends(require_permission("integrations:read"))])
async def list_agents(session: SessionDep):
    result = await session.execute(select(WazuhAgent).order_by(WazuhAgent.hostname))
    return result.scalars().all()


@router.post("/sync", dependencies=[Depends(require_permission("integrations:write"))])
async def sync(request: Request, background_tasks: BackgroundTasks):
    creds = request.app.state.wazuh_creds
    session_factory = request.app.state.session_factory
    health = request.app.state.source_health
    background_tasks.add_task(
        _do_sync, session_factory, health, creds["url"], creds["username"], creds["password"]
    )
    return {"status": "running"}


async def _do_sync(session_factory, health, url, username, password):
    async with session_factory() as session:
        await sync_wazuh(session, health, url, username, password)
