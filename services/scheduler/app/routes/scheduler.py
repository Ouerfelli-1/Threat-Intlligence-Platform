import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_db import get_session

from app.db import get_session_factory
from app.jobs import JOB_CONFIGS, complete_run
from app.models import JobRunHistory
from app.schemas import CompleteRunBody, JobInfo, RunOut

router = APIRouter(tags=["scheduler"])


async def _session_dep():
    # async-generator wrapper: FastAPI iterates exactly once,
    # yielding the live session into the endpoint.
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


@router.get("/jobs", response_model=list[JobInfo], dependencies=[Depends(require_permission("scheduling:read"))])
async def list_jobs(request: Request):
    scheduler = request.app.state.scheduler
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append(JobInfo(
            id=job.id,
            next_run_time=job.next_run_time,
            trigger=str(job.trigger),
        ))
    return jobs


@router.get("/jobs/{job_id}", dependencies=[Depends(require_permission("scheduling:read"))])
async def get_job(job_id: str, request: Request, session: SessionDep):
    scheduler = request.app.state.scheduler
    job = scheduler.get_job(job_id)
    if not job:
        from tip_common import NotFoundError
        raise NotFoundError(f"Job {job_id} not found")

    runs_result = await session.execute(
        select(JobRunHistory)
        .where(JobRunHistory.job_id == job_id)
        .order_by(JobRunHistory.triggered_at.desc())
        .limit(20)
    )
    runs = runs_result.scalars().all()

    return {
        "id": job.id,
        "next_run_time": job.next_run_time,
        "trigger": str(job.trigger),
        "recent_runs": [RunOut.model_validate(r) for r in runs],
    }


@router.post("/jobs/{job_id}/trigger", dependencies=[Depends(require_permission("scheduling:write"))])
async def trigger_job(job_id: str, request: Request):
    scheduler = request.app.state.scheduler
    job = scheduler.get_job(job_id)
    if not job:
        from tip_common import NotFoundError
        raise NotFoundError(f"Job {job_id} not found")
    scheduler.modify_job(job_id, next_run_time=datetime.now())
    return {"status": "triggered", "job_id": job_id}


@router.get("/runs", response_model=list[RunOut], dependencies=[Depends(require_permission("scheduling:read"))])
async def list_runs(
    session: SessionDep,
    job_id: str | None = Query(None),
    status: str | None = Query(None),
    since: datetime | None = Query(None),
    limit: int = Query(50, le=200),
):
    stmt = select(JobRunHistory)
    if job_id:
        stmt = stmt.where(JobRunHistory.job_id == job_id)
    if status:
        stmt = stmt.where(JobRunHistory.status == status)
    if since:
        stmt = stmt.where(JobRunHistory.triggered_at >= since)
    stmt = stmt.order_by(JobRunHistory.triggered_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/internal/runs/{run_id}/complete")
async def complete_run_callback(run_id: uuid.UUID, body: CompleteRunBody):
    """Called by slow jobs to report completion."""
    await complete_run(run_id, body.status, body.error)
    return {"ok": True}
