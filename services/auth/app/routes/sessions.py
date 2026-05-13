import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session_factory
from app.deps import require_admin
from app.models import Session as DBSession
from app.schemas import SessionOut

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _get_session() -> AsyncSession:
    async with get_session_factory()() as s:
        yield s


SessionDep = Annotated[AsyncSession, Depends(_get_session)]


@router.get("", response_model=list[SessionOut], dependencies=[Depends(require_admin)])
async def list_sessions(session: SessionDep, user_id: uuid.UUID | None = None):
    stmt = select(DBSession).where(DBSession.revoked == False)
    if user_id:
        stmt = stmt.where(DBSession.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.delete("/{session_id}", status_code=204, dependencies=[Depends(require_admin)])
async def revoke_session(session_id: uuid.UUID, session: SessionDep):
    db_session = await session.get(DBSession, session_id)
    if not db_session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    db_session.revoked = True
    await session.commit()
