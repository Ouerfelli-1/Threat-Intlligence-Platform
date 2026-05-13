import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_common import ConflictError, NotFoundError

from app.db import get_session
from app.models import Feed
from app.schemas import FeedCreate, FeedOut, FeedUpdate

router = APIRouter(prefix="/feeds", tags=["feeds"])


@router.get("", response_model=list[FeedOut], dependencies=[Depends(require_permission("intelligence:read"))])
async def list_feeds(session: AsyncSession = Depends(get_session)) -> list[FeedOut]:
    rows = (await session.execute(select(Feed).order_by(Feed.name))).scalars().all()
    return [FeedOut.model_validate(r) for r in rows]


@router.post(
    "",
    response_model=FeedOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("intelligence:write"))],
)
async def create_feed(body: FeedCreate, session: AsyncSession = Depends(get_session)) -> FeedOut:
    existing = await session.scalar(select(Feed).where(Feed.url == body.url))
    if existing:
        raise ConflictError(f"feed url already registered: {body.url}")
    feed = Feed(**body.model_dump())
    session.add(feed)
    await session.flush()
    return FeedOut.model_validate(feed)


@router.patch(
    "/{feed_id}",
    response_model=FeedOut,
    dependencies=[Depends(require_permission("intelligence:write"))],
)
async def update_feed(
    feed_id: uuid.UUID, body: FeedUpdate, session: AsyncSession = Depends(get_session)
) -> FeedOut:
    feed = await session.get(Feed, feed_id)
    if feed is None:
        raise NotFoundError(f"feed {feed_id} not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(feed, k, v)
    await session.flush()
    return FeedOut.model_validate(feed)


@router.delete(
    "/{feed_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("intelligence:write"))],
)
async def delete_feed(feed_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> None:
    feed = await session.get(Feed, feed_id)
    if feed is None:
        raise NotFoundError(f"feed {feed_id} not found")
    await session.delete(feed)
