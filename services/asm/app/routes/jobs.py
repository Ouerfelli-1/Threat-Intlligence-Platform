from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_db import get_session

from app.db import get_session_factory
from app.models import Finding, Job
from app.scanner import run_scan
from app.schemas import FindingOut, JobOut

router = APIRouter(tags=["jobs"])


async def _session_dep():
    # async-generator wrapper: FastAPI iterates exactly once,
    # yielding the live session into the endpoint.
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


@router.get("/jobs", response_model=list[JobOut], dependencies=[Depends(require_permission("asm:read"))])
async def list_jobs(
    session: SessionDep,
    status: str | None = Query(None),
    limit: int = Query(20, le=100),
):
    stmt = select(Job)
    if status:
        stmt = stmt.where(Job.status == status)
    stmt = stmt.order_by(Job.started_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/jobs/{job_id}", response_model=JobOut, dependencies=[Depends(require_permission("asm:read"))])
async def get_job(job_id: UUID, session: SessionDep):
    from tip_common import NotFoundError

    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    return job


@router.get("/findings", response_model=list[FindingOut], dependencies=[Depends(require_permission("asm:read"))])
async def list_findings(
    session: SessionDep,
    scope_id: UUID | None = Query(None),
    type: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    stmt = select(Finding)
    if type:
        stmt = stmt.where(Finding.type == type)
    stmt = stmt.order_by(Finding.discovered_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/scan/run", status_code=202, dependencies=[Depends(require_permission("asm:write"))])
async def trigger_scan(request: Request, background_tasks: BackgroundTasks):
    session_factory = request.app.state.session_factory
    health = request.app.state.source_health
    shodan_key = getattr(request.app.state, "shodan_api_key", "")
    background_tasks.add_task(run_scan, session_factory, health, shodan_key)
    return {"status": "running"}
