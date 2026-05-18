import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session_factory
from app.deps import require_admin
from app.models import Session as DBSession
from app.models import User
from app.schemas import SessionOut

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _get_session() -> AsyncSession:
    async with get_session_factory()() as s:
        yield s


SessionDep = Annotated[AsyncSession, Depends(_get_session)]


def _to_out(db_session: DBSession, username: str | None) -> dict:
    return {
        "id": db_session.id,
        "user_id": db_session.user_id,
        "username": username,
        "issued_at": db_session.issued_at,
        "expires_at": db_session.expires_at,
        "revoked": db_session.revoked,
        "user_agent": db_session.user_agent,
        "ip": db_session.ip,
    }


@router.get("", response_model=list[SessionOut], dependencies=[Depends(require_admin)])
async def list_sessions(
    session: SessionDep,
    user_id: uuid.UUID | None = None,
    include_revoked: bool = False,
):
    stmt = select(DBSession).options(selectinload(DBSession.user))
    if not include_revoked:
        stmt = stmt.where(DBSession.revoked == False)  # noqa: E712
    if user_id:
        stmt = stmt.where(DBSession.user_id == user_id)
    stmt = stmt.order_by(DBSession.issued_at.desc())
    result = await session.execute(stmt)
    return [_to_out(s, s.user.username if s.user else None) for s in result.scalars().all()]


@router.delete("/{session_id}", status_code=204, dependencies=[Depends(require_admin)])
async def revoke_session(session_id: uuid.UUID, session: SessionDep):
    db_session = await session.get(DBSession, session_id)
    if not db_session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    db_session.revoked = True
    await session.commit()


@router.post("/revoke-all", status_code=204, dependencies=[Depends(require_admin)])
async def revoke_all_sessions(session: SessionDep):
    """Mark every active session as revoked. Useful for emergency lockout."""
    await session.execute(
        update(DBSession).where(DBSession.revoked == False).values(revoked=True)  # noqa: E712
    )
    await session.commit()
