import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_common import NotFoundError

from app.db import get_session
from app.models import Article
from app.schemas import ArticleList, ArticleOut

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get(
    "",
    response_model=ArticleList,
    dependencies=[Depends(require_permission("intelligence:read"))],
)
async def list_articles(
    q: str | None = Query(None, description="Free-text match on title/summary"),
    source: str | None = None,
    tag: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    last: str | None = Query(None, description="Shortcut: 1h, 24h, 7d"),
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> ArticleList:
    stmt = select(Article)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Article.title.ilike(like), Article.summary.ilike(like)))
    if source:
        stmt = stmt.where(Article.source_name == source)
    if tag:
        stmt = stmt.where(Article.tags.any(tag))
    if last and since is None:
        delta_map = {"h": 1, "d": 24}
        unit = last[-1]
        try:
            qty = int(last[:-1])
        except ValueError:
            qty = 0
        if unit in delta_map and qty > 0:
            since = datetime.now(timezone.utc) - timedelta(hours=delta_map[unit] * qty)
    if since:
        stmt = stmt.where(Article.fetched_at >= since)
    if until:
        stmt = stmt.where(Article.fetched_at <= until)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Article.fetched_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return ArticleList(items=[ArticleOut.model_validate(r) for r in rows], total=total)


@router.get(
    "/{article_id}",
    response_model=ArticleOut,
    dependencies=[Depends(require_permission("intelligence:read"))],
)
async def get_article(
    article_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ArticleOut:
    article = await session.get(Article, article_id)
    if article is None:
        raise NotFoundError(f"article {article_id} not found")
    return ArticleOut.model_validate(article)
