"""Factory for per-resource analyst notes CRUD routers.

Each service calls ``build_notes_router(...)`` once and includes the returned
``APIRouter`` in its app.  The factory produces four endpoints:

    GET    /<prefix>/{resource_id_param}/notes
    POST   /<prefix>/{resource_id_param}/notes
    PATCH  /<prefix>/{resource_id_param}/notes/{note_id}
    DELETE /<prefix>/{resource_id_param}/notes/{note_id}

Notes are sorted ``pinned DESC, created_at DESC`` by default.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from tip_common.errors import NotFoundError


# ---- Pydantic schemas (shared across all services) ----

class NoteIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=10000)
    pinned: bool = False


class NoteUpdate(BaseModel):
    body: str | None = Field(None, min_length=1, max_length=10000)
    pinned: bool | None = None


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    body: str
    pinned: bool
    author: str
    created_at: datetime
    updated_at: datetime


class NoteList(BaseModel):
    items: list[NoteOut]
    total: int


# ---- Factory ----

def build_notes_router(
    *,
    prefix: str,
    resource_id_param: str,
    note_model: Any,
    resource_id_column: str,
    perm_read: str,
    perm_write: str,
    get_session: Callable,
    tags: list[str] | None = None,
) -> APIRouter:
    """Build a 4-endpoint CRUD router for analyst notes on a resource.

    Parameters
    ----------
    prefix : str
        URL prefix *including* the resource segment, e.g. ``"/articles"`` so
        the notes live at ``/articles/{article_id}/notes``.
    resource_id_param : str
        The path-parameter name, e.g. ``"article_id"``.
    note_model : SQLAlchemy ORM class
        Must have columns: ``id``, ``<resource_id_column>``, ``body``,
        ``pinned``, ``author``, ``created_at``, ``updated_at``.
    resource_id_column : str
        Column on *note_model* that holds the FK to the resource, e.g.
        ``"article_id"``.
    perm_read, perm_write : str
        Permission strings checked via ``require_permission``.
    get_session : callable
        FastAPI dependency that yields an ``AsyncSession``.
    tags : list[str] | None
        OpenAPI tags for the router.
    """
    # Lazy import so services that don't install tip_auth (e.g. auth itself)
    # can still import tip_common without crashing.
    from tip_auth import current_user, require_permission, AuthContext  # noqa: F811

    router = APIRouter(tags=tags or ["notes"])
    fk_col = getattr(note_model, resource_id_column)

    def _extract_rid(request: Request) -> str:
        return request.path_params[resource_id_param]

    def _coerce_rid(raw: str):
        """If the column type is UUID, parse it; otherwise keep as string."""
        try:
            return uuid.UUID(raw)
        except (ValueError, AttributeError):
            return raw

    @router.get(
        f"{prefix}/{{{resource_id_param}}}/notes",
        response_model=NoteList,
        dependencies=[Depends(require_permission(perm_read))],
        name=f"list_{resource_id_param}_notes",
    )
    async def list_notes(
        request: Request,
        pinned_only: bool = Query(False),
        limit: int = Query(50, le=200),
        offset: int = 0,
        session: AsyncSession = Depends(get_session),
    ) -> NoteList:
        rid = _coerce_rid(_extract_rid(request))
        stmt = select(note_model).where(fk_col == rid)
        if pinned_only:
            stmt = stmt.where(note_model.pinned.is_(True))
        total = (await session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        stmt = (
            stmt.order_by(note_model.pinned.desc(), note_model.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await session.execute(stmt)).scalars().all()
        return NoteList(items=[NoteOut.model_validate(r) for r in rows], total=total)

    @router.post(
        f"{prefix}/{{{resource_id_param}}}/notes",
        response_model=NoteOut,
        status_code=201,
        dependencies=[Depends(require_permission(perm_write))],
        name=f"create_{resource_id_param}_note",
    )
    async def create_note(
        request: Request,
        body: NoteIn,
        ctx: AuthContext = Depends(current_user),
        session: AsyncSession = Depends(get_session),
    ) -> NoteOut:
        rid = _coerce_rid(_extract_rid(request))
        now = datetime.now(timezone.utc)
        note = note_model(
            id=uuid.uuid4(),
            **{resource_id_column: rid},
            body=body.body,
            pinned=body.pinned,
            author=ctx.subject,
            created_at=now,
            updated_at=now,
        )
        session.add(note)
        await session.flush()
        return NoteOut.model_validate(note)

    @router.patch(
        f"{prefix}/{{{resource_id_param}}}/notes/{{note_id}}",
        response_model=NoteOut,
        dependencies=[Depends(require_permission(perm_write))],
        name=f"update_{resource_id_param}_note",
    )
    async def update_note(
        request: Request,
        note_id: uuid.UUID,
        body: NoteUpdate,
        session: AsyncSession = Depends(get_session),
    ) -> NoteOut:
        rid = _coerce_rid(_extract_rid(request))
        note = await session.get(note_model, note_id)
        if note is None or str(getattr(note, resource_id_column)) != str(rid):
            raise NotFoundError(f"note {note_id} not found")
        if body.body is not None:
            note.body = body.body
        if body.pinned is not None:
            note.pinned = body.pinned
        note.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return NoteOut.model_validate(note)

    @router.delete(
        f"{prefix}/{{{resource_id_param}}}/notes/{{note_id}}",
        status_code=204,
        dependencies=[Depends(require_permission(perm_write))],
        name=f"delete_{resource_id_param}_note",
    )
    async def delete_note(
        request: Request,
        note_id: uuid.UUID,
        session: AsyncSession = Depends(get_session),
    ) -> None:
        rid = _coerce_rid(_extract_rid(request))
        note = await session.get(note_model, note_id)
        if note is None or str(getattr(note, resource_id_column)) != str(rid):
            raise NotFoundError(f"note {note_id} not found")
        await session.delete(note)
        await session.flush()

    return router
