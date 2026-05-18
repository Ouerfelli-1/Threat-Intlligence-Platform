from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_db import get_session

from app.db import get_session_factory
from app.models import Scope
from app.schemas import ScopeCreate, ScopeOut, ScopeUpdate

router = APIRouter(prefix="/scopes", tags=["scopes"])


async def _session_dep():
    # async-generator wrapper: FastAPI iterates exactly once,
    # yielding the live session into the endpoint.
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


@router.get("", response_model=list[ScopeOut], dependencies=[Depends(require_permission("asm:read"))])
async def list_scopes(session: SessionDep):
    result = await session.execute(select(Scope).order_by(Scope.name))
    return result.scalars().all()


@router.post("", response_model=ScopeOut, status_code=201, dependencies=[Depends(require_permission("asm:write"))])
async def create_scope(body: ScopeCreate, session: SessionDep):
    import uuid
    scope = Scope(id=uuid.uuid4(), **body.model_dump())
    session.add(scope)
    await session.commit()
    return scope


@router.get("/{scope_id}", response_model=ScopeOut, dependencies=[Depends(require_permission("asm:read"))])
async def get_scope(scope_id: UUID, session: SessionDep):
    from tip_common import NotFoundError

    result = await session.execute(select(Scope).where(Scope.id == scope_id))
    scope = result.scalar_one_or_none()
    if not scope:
        raise NotFoundError(f"Scope {scope_id} not found")
    return scope


@router.patch("/{scope_id}", response_model=ScopeOut, dependencies=[Depends(require_permission("asm:write"))])
async def update_scope(scope_id: UUID, body: ScopeUpdate, session: SessionDep):
    """Partial update. Most common use-case is the pause/resume toggle
    (`active=false` halts scanning for this scope until re-enabled).
    Targets + findings are preserved across a pause cycle.
    """
    from tip_common import NotFoundError

    result = await session.execute(select(Scope).where(Scope.id == scope_id))
    scope = result.scalar_one_or_none()
    if not scope:
        raise NotFoundError(f"Scope {scope_id} not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(scope, k, v)
    await session.commit()
    return scope


@router.delete("/{scope_id}", status_code=204, dependencies=[Depends(require_permission("asm:write"))])
async def delete_scope(scope_id: UUID, session: SessionDep):
    """Delete a scope and all of its derivative data.

    Cascade chain (enforced at the DB level by FKs):
      Scope -> Target  (ondelete=CASCADE)
      Scope -> Job     (ondelete=CASCADE, set up in migration 0002)
      Job   -> Finding (ondelete=CASCADE)

    Before migration 0002 the Scope -> Job FK was SET NULL, which orphaned
    findings forever. With CASCADE in place, a single delete here clears
    every row tied to the scope in one transaction.
    """
    from tip_common import NotFoundError

    result = await session.execute(select(Scope).where(Scope.id == scope_id))
    scope = result.scalar_one_or_none()
    if not scope:
        raise NotFoundError(f"Scope {scope_id} not found")
    await session.delete(scope)
    await session.commit()
