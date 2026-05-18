from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_db import get_session

from app.db import get_session_factory
from app.models import Target
from app.schemas import TargetCreate, TargetOut, TargetUpdate

router = APIRouter(prefix="/targets", tags=["targets"])


async def _session_dep():
    # async-generator wrapper: FastAPI iterates exactly once,
    # yielding the live session into the endpoint.
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


@router.get("", response_model=list[TargetOut], dependencies=[Depends(require_permission("asm:read"))])
async def list_targets(
    session: SessionDep,
    scope_id: UUID | None = Query(None),
    type: str | None = Query(None),
):
    stmt = select(Target)
    if scope_id:
        stmt = stmt.where(Target.scope_id == scope_id)
    if type:
        stmt = stmt.where(Target.type == type)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=TargetOut, status_code=201, dependencies=[Depends(require_permission("asm:write"))])
async def create_target(body: TargetCreate, session: SessionDep):
    import uuid
    target = Target(id=uuid.uuid4(), **body.model_dump())
    session.add(target)
    await session.commit()
    return target


@router.patch("/{target_id}", response_model=TargetOut, dependencies=[Depends(require_permission("asm:write"))])
async def update_target(target_id: UUID, body: TargetUpdate, session: SessionDep):
    """Partial update — most-used path is the pause/resume toggle (active).

    Inactive targets stay in the DB; the scanner just skips them. This way an
    analyst can pause noisy targets without losing their history or having to
    re-add them to resume scanning.
    """
    from tip_common import NotFoundError

    result = await session.execute(select(Target).where(Target.id == target_id))
    target = result.scalar_one_or_none()
    if not target:
        raise NotFoundError(f"Target {target_id} not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(target, field, value)
    await session.commit()
    return target


@router.delete("/{target_id}", status_code=204, dependencies=[Depends(require_permission("asm:write"))])
async def delete_target(target_id: UUID, session: SessionDep):
    from tip_common import NotFoundError

    result = await session.execute(select(Target).where(Target.id == target_id))
    target = result.scalar_one_or_none()
    if not target:
        raise NotFoundError(f"Target {target_id} not found")
    await session.delete(target)
    await session.commit()
