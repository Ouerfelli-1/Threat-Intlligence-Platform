import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_common import NotFoundError, resolve_sort

from app.db import get_session
from app.models import Article, ArticleInsight
from app.schemas import (
    AnalystStatusUpdate,
    AnalyzeRequest,
    ArticleList,
    ArticleOut,
    InsightOut,
    InsightOverrideIn,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/articles", tags=["articles"])


_ARTICLE_SORT_COLS = {
    "fetched_at":       Article.fetched_at,
    "published_at":     Article.published_at,
    "title":            Article.title,
    "source_name":      Article.source_name,
    "confidence_score": Article.confidence_score,
    "analyst_status":   Article.analyst_status,
}


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
    include_not_relevant: bool = Query(False, description="Include not_relevant items"),
    sort_by: str | None = Query(None, description=f"One of: {', '.join(sorted(_ARTICLE_SORT_COLS))}"),
    sort_dir: str | None = Query(None, description="asc | desc"),
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> ArticleList:
    stmt = select(Article)
    if not include_not_relevant:
        stmt = stmt.where(Article.analyst_status != "not_relevant")
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
    stmt = stmt.order_by(
        resolve_sort(sort_by, sort_dir, _ARTICLE_SORT_COLS, default="fetched_at")
    ).limit(limit).offset(offset)
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


@router.patch(
    "/{article_id}/status",
    response_model=ArticleOut,
    dependencies=[Depends(require_permission("intelligence:write"))],
)
async def update_article_status(
    article_id: uuid.UUID,
    body: AnalystStatusUpdate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> ArticleOut:
    article = await session.get(Article, article_id)
    if article is None:
        raise NotFoundError(f"article {article_id} not found")
    old_status = article.analyst_status
    article.analyst_status = body.analyst_status
    await session.flush()

    # When marked 'relevant', check insight for products_mentioned and auto-add
    if body.analyst_status == "relevant" and old_status != "relevant":
        insight = await session.get(ArticleInsight, article_id)
        products = _extract_products_from_insight(insight)
        if products:
            from app.settings import get_settings
            settings = get_settings()
            jwt = getattr(request.app.state, "service_jwt", "") or ""
            for product in products:
                background_tasks.add_task(
                    _auto_add_product, settings.cmdb_url, jwt, "article", str(article_id), product
                )

    return ArticleOut.model_validate(article)


def _extract_products_from_insight(insight) -> list[str]:
    """Extract products_mentioned from article AI insight payload."""
    if insight is None:
        return []
    payload = insight.payload or {}
    products = payload.get("products_mentioned", [])
    if isinstance(products, list):
        return [p for p in products if isinstance(p, str)][:5]
    return []


async def _auto_add_product(
    cmdb_url: str, jwt: str, resource_type: str, resource_id: str, product_name: str
) -> None:
    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=10) as c:
            r = await c.post(
                f"{cmdb_url}/profile/auto-add",
                json={
                    "source_resource_type": resource_type,
                    "source_resource_id": resource_id,
                    "product_name": product_name,
                },
            )
            if r.status_code < 300:
                log.info("Auto-added product '%s' from %s %s", product_name, resource_type, resource_id)
            else:
                log.warning("CMDB auto-add returned %d: %s", r.status_code, r.text[:200])
    except Exception:
        log.exception("Failed to auto-add product '%s' to CMDB", product_name)


@router.get(
    "/{article_id}/insight",
    response_model=InsightOut,
    dependencies=[Depends(require_permission("intelligence:read"))],
)
async def get_article_insight(
    article_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> InsightOut:
    insight = await session.get(ArticleInsight, article_id)
    if insight is None:
        raise NotFoundError(f"no insight for article {article_id}")
    return InsightOut.model_validate(insight)


@router.put(
    "/{article_id}/insight/override",
    response_model=InsightOut,
    dependencies=[Depends(require_permission("intelligence:write"))],
)
async def override_article_insight(
    article_id: uuid.UUID,
    body: InsightOverrideIn,
    session: AsyncSession = Depends(get_session),
) -> InsightOut:
    insight = await session.get(ArticleInsight, article_id)
    if insight is None:
        raise NotFoundError(f"no insight for article {article_id}")
    insight.analyst_override = body.analyst_override
    await session.flush()
    return InsightOut.model_validate(insight)


@router.post(
    "/{article_id}/analyze",
    status_code=202,
    dependencies=[Depends(require_permission("intelligence:write"))],
)
async def analyze_article(
    article_id: uuid.UUID,
    request: Request,
    body: AnalyzeRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Trigger on-demand AI analysis on this article via the orchestrator."""
    from app.settings import get_settings

    article = await session.get(Article, article_id)
    if article is None:
        raise NotFoundError(f"article {article_id} not found")
    if body is None:
        body = AnalyzeRequest()

    settings = get_settings()
    jwt = getattr(request.app.state, "service_jwt", "")
    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}

    actions = body.actions or ["extract_iocs", "map_ttps"]
    if body.flowviz:
        actions = list(set(actions) | {"flowviz"})

    async with httpx.AsyncClient(headers=headers, timeout=30) as c:
        r = await c.post(
            f"{settings.orchestrator_url}/actions/run",
            json={
                "resource_type": "article",
                "resource_id": str(article_id),
                "actions": actions,
            },
        )
        return r.json()
