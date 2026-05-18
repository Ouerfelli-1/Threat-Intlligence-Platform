"""Tag catalog CRUD.

Reads are open to anyone with `assets:read` (so analysts can populate
tag-pickers in forms across the platform). Writes are admin-only via
`assets:write`.

Filtering by scope is the primary read path:
    GET /tags?scope=ioc       -> tags whose `scopes` array contains 'ioc'
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import AuthContext, current_user, require_permission
from tip_common import ConflictError, NotFoundError

from app.db import get_session
from app.models import TagCatalog
from app.schemas import TAG_SCOPES, TagCreate, TagOut, TagUpdate

router = APIRouter(prefix="/tags", tags=["tags"])


def _validate_scopes(scopes: list[str] | None) -> None:
    if not scopes:
        return
    invalid = [s for s in scopes if s not in TAG_SCOPES]
    if invalid:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"invalid scope(s): {invalid}. Allowed: {sorted(TAG_SCOPES)}",
        )


@router.get(
    "",
    response_model=list[TagOut],
    dependencies=[Depends(require_permission("assets:read"))],
)
async def list_tags(
    scope: str | None = Query(None, description="If set, only tags whose scopes[] contains this value"),
    session: AsyncSession = Depends(get_session),
) -> list[TagOut]:
    stmt = select(TagCatalog).order_by(TagCatalog.name)
    if scope:
        if scope not in TAG_SCOPES:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"invalid scope '{scope}'. Allowed: {sorted(TAG_SCOPES)}",
            )
        stmt = stmt.where(TagCatalog.scopes.any(scope))
    rows = (await session.execute(stmt)).scalars().all()
    return [TagOut.model_validate(r) for r in rows]


@router.post(
    "",
    response_model=TagOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("assets:write"))],
)
async def create_tag(
    body: TagCreate,
    ctx: AuthContext = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> TagOut:
    """Create a tag, or return the existing one if the name already exists.

    Made idempotent on purpose: the analyst hits "Add" from a tag-picker
    popover and shouldn't get a 409 just because someone added the same
    label earlier. Returns 201 for a fresh insert and 200 for an existing
    match (FastAPI status_code is the default; we override via Response).

    Matching is case-insensitive + whitespace-trimmed so "Ransomware ",
    "ransomware", and "RANSOMWARE" all resolve to one row.
    """
    from fastapi import Response
    from sqlalchemy import func

    _validate_scopes(body.scopes)
    name_norm = (body.name or "").strip()
    if not name_norm:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tag name is required")

    existing = await session.scalar(
        select(TagCatalog).where(func.lower(TagCatalog.name) == name_norm.lower())
    )
    if existing:
        # Return the existing tag with 200 (not 201) so the client can
        # distinguish "created" from "already there". Either way the picker
        # ends up with a usable tag id.
        return Response(
            content=TagOut.model_validate(existing).model_dump_json(),
            media_type="application/json",
            status_code=status.HTTP_200_OK,
        )

    tag = TagCatalog(
        id=uuid.uuid4(),
        name=name_norm,
        description=body.description,
        color=body.color,
        scopes=body.scopes,
        created_by=ctx.subject if ctx else None,
    )
    session.add(tag)
    await session.flush()
    return TagOut.model_validate(tag)


@router.patch(
    "/{tag_id}",
    response_model=TagOut,
    dependencies=[Depends(require_permission("assets:write"))],
)
async def update_tag(
    tag_id: uuid.UUID,
    body: TagUpdate,
    session: AsyncSession = Depends(get_session),
) -> TagOut:
    tag = await session.get(TagCatalog, tag_id)
    if tag is None:
        raise NotFoundError(f"tag {tag_id} not found")
    _validate_scopes(body.scopes)
    if body.name is not None and body.name != tag.name:
        # Disallow rename collision
        collide = await session.scalar(select(TagCatalog).where(TagCatalog.name == body.name))
        if collide and collide.id != tag_id:
            raise ConflictError(f"tag '{body.name}' already exists")
        tag.name = body.name.strip()
    if body.description is not None:
        tag.description = body.description
    if body.color is not None:
        tag.color = body.color
    if body.scopes is not None:
        tag.scopes = body.scopes
    tag.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return TagOut.model_validate(tag)


@router.delete(
    "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("assets:write"))],
)
async def delete_tag(
    tag_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    tag = await session.get(TagCatalog, tag_id)
    if tag is None:
        raise NotFoundError(f"tag {tag_id} not found")
    await session.delete(tag)
