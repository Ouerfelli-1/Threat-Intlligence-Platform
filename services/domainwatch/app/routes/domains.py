import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_db import get_session

from app.db import get_session_factory
from app.models import Change, Domain, Snapshot
from app.monitor.jobs import _monitor_domain
from app.schemas import ChangeOut, DomainCreate, DomainOut, DomainUpdate, SnapshotOut

router = APIRouter(prefix="/domains", tags=["domains"])


async def _session_dep():
    # async-generator wrapper: FastAPI iterates exactly once,
    # yielding the live session into the endpoint.
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


@router.get("", response_model=list[DomainOut], dependencies=[Depends(require_permission("domainwatch:read"))])
async def list_domains(session: SessionDep):
    result = await session.execute(select(Domain).order_by(Domain.name))
    return result.scalars().all()


@router.post("", response_model=DomainOut, status_code=201, dependencies=[Depends(require_permission("domainwatch:write"))])
async def create_domain(body: DomainCreate, session: SessionDep):
    from fastapi import HTTPException
    name = body.name.lower().strip()
    # Return existing domain if already tracked (idempotent creation)
    existing = (await session.execute(select(Domain).where(Domain.name == name))).scalar_one_or_none()
    if existing:
        return existing
    domain = Domain(id=uuid.uuid4(), name=name)
    session.add(domain)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        # Another concurrent request inserted it — fetch and return it
        existing = (await session.execute(select(Domain).where(Domain.name == name))).scalar_one_or_none()
        if existing:
            return existing
        raise HTTPException(status_code=409, detail=f"Domain '{name}' already exists")
    return domain


@router.delete("/{domain_id}", status_code=204, dependencies=[Depends(require_permission("domainwatch:write"))])
async def delete_domain(domain_id: UUID, session: SessionDep):
    from tip_common import NotFoundError

    result = await session.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()
    if not domain:
        raise NotFoundError(f"Domain {domain_id} not found")
    await session.delete(domain)
    await session.commit()


@router.patch("/{domain_id}", response_model=DomainOut, dependencies=[Depends(require_permission("domainwatch:write"))])
async def update_domain(domain_id: UUID, body: DomainUpdate, session: SessionDep):
    """Toggle archive state. Setting active=false stops the scheduler from
    visiting the domain; setting active=true puts it back on the watch list."""
    from tip_common import NotFoundError

    result = await session.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()
    if not domain:
        raise NotFoundError(f"Domain {domain_id} not found")
    if body.active is not None:
        domain.active = body.active
    await session.commit()
    return domain


@router.get("/{domain_id}", response_model=DomainOut, dependencies=[Depends(require_permission("domainwatch:read"))])
async def get_domain(domain_id: UUID, session: SessionDep):
    from tip_common import NotFoundError

    result = await session.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()
    if not domain:
        raise NotFoundError(f"Domain {domain_id} not found")
    return domain


@router.get("/{domain_id}/snapshots", response_model=list[SnapshotOut], dependencies=[Depends(require_permission("domainwatch:read"))])
async def list_snapshots(domain_id: UUID, session: SessionDep, limit: int = Query(20, le=100)):
    result = await session.execute(
        select(Snapshot).where(Snapshot.domain_id == domain_id).order_by(Snapshot.captured_at.desc()).limit(limit)
    )
    return result.scalars().all()


@router.get("/{domain_id}/snapshots/{snapshot_id}", response_model=SnapshotOut, dependencies=[Depends(require_permission("domainwatch:read"))])
async def get_snapshot(domain_id: UUID, snapshot_id: UUID, session: SessionDep):
    from tip_common import NotFoundError

    result = await session.execute(
        select(Snapshot).where(Snapshot.id == snapshot_id, Snapshot.domain_id == domain_id)
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise NotFoundError(f"Snapshot {snapshot_id} not found")
    return snapshot


@router.get("/{domain_id}/changes", response_model=list[ChangeOut], dependencies=[Depends(require_permission("domainwatch:read"))])
async def list_changes(
    domain_id: UUID, session: SessionDep, since: datetime | None = Query(None)
):
    stmt = select(Change).where(Change.domain_id == domain_id)
    if since:
        stmt = stmt.where(Change.detected_at >= since)
    stmt = stmt.order_by(Change.detected_at.desc()).limit(100)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/{domain_id}/screenshot", dependencies=[Depends(require_permission("domainwatch:read"))])
async def latest_screenshot(domain_id: UUID, session: SessionDep):
    from tip_common import NotFoundError

    result = await session.execute(
        select(Snapshot)
        .where(Snapshot.domain_id == domain_id, Snapshot.screenshot_path.is_not(None))
        .order_by(Snapshot.captured_at.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()
    if not snap or not snap.screenshot_path:
        raise NotFoundError("No screenshot available for this domain")
    return FileResponse(snap.screenshot_path, media_type="image/png")


@router.post("/{domain_id}/check", status_code=202, dependencies=[Depends(require_permission("domainwatch:write"))])
async def manual_check(domain_id: UUID, request: Request, session: SessionDep, background_tasks: BackgroundTasks):
    from tip_common import NotFoundError

    result = await session.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()
    if not domain:
        raise NotFoundError(f"Domain {domain_id} not found")

    run_id = str(uuid.uuid4())
    background_tasks.add_task(
        _do_manual_check,
        request.app.state.session_factory,
        domain,
        request.app.state.settings.screenshot_dir,
    )
    return {"status": "running", "run_id": run_id}


async def _do_manual_check(session_factory, domain, screenshot_dir):
    async with session_factory() as session:
        await _monitor_domain(session, domain, screenshot_dir)
