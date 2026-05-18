import asyncio
import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse, urlunparse

import feedparser
from bs4 import BeautifulSoup
from readability import Document
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tip_common.logging_setup import get_logger
from tip_http import build_resilient_client, fetch_with_resilience
from tip_schemas import (
    SOURCE_RELIABILITY,
    ConfidenceInputs,
    DataType,
    compute_confidence,
)
from tip_source_health import SourceHealthRepository

from app.models import Article, ArticleInsight, Feed

logger = get_logger("news.ingest")

TAG_PATTERNS = [
    (re.compile(r"\bransomware\b", re.I), "ransomware"),
    (re.compile(r"\bcve-\d{4}-\d+\b", re.I), "cve"),
    (re.compile(r"\bphish(ing)?\b", re.I), "phishing"),
    (re.compile(r"\bapt\d+\b", re.I), "apt"),
    (re.compile(r"\bzero[- ]?day\b", re.I), "zero_day"),
    (re.compile(r"\bsupply[- ]chain\b", re.I), "supply_chain"),
    (re.compile(r"\bdata[- ]?breach\b", re.I), "data_breach"),
    (re.compile(r"\bbackdoor\b", re.I), "backdoor"),
]


def _canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), netloc, path, "", "", ""))


def _hash_url(url: str) -> str:
    return hashlib.sha256(_canonicalize_url(url).encode("utf-8")).hexdigest()


def _strip_html(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()


def _extract_main_content(html: str) -> str:
    try:
        doc = Document(html or "")
        return _strip_html(doc.summary())
    except Exception:
        return _strip_html(html)


def _detect_tags(text: str) -> list[str]:
    found = set()
    for pat, tag in TAG_PATTERNS:
        if pat.search(text or ""):
            found.add(tag)
    return sorted(found)


def _parse_pub_date(entry: dict) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        ts = entry.get(key)
        if ts is None:
            continue
        try:
            return datetime(*ts[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
    return None


async def _fetch_feed_text(client_factory, feed_url: str, *, user_agent: str) -> str:
    async with client_factory() as client:
        headers = {"User-Agent": user_agent, "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8"}
        resp = await client.client.get(feed_url, headers=headers)
        resp.raise_for_status()
        return resp.text


def _build_article(
    *,
    entry: dict,
    feed: Feed,
    source_name: str,
    reliability: float,
) -> dict | None:
    """Returns a dict of column values, or None if the entry is unusable."""
    url = entry.get("link")
    title = entry.get("title")
    if not url or not title:
        return None

    published_at = _parse_pub_date(entry)
    summary_html = entry.get("summary") or entry.get("description") or ""
    content_html = ""
    contents = entry.get("content") or []
    if isinstance(contents, list) and contents:
        content_html = contents[0].get("value", "")
    main_text = _extract_main_content(content_html or summary_html)

    extraction_quality = 1.0 if (content_html or summary_html) else 0.5
    days_since = 0.0 if published_at is None else max(
        0.0, (datetime.now(timezone.utc) - published_at).total_seconds() / 86400.0
    )
    confidence_inputs = ConfidenceInputs(
        source_reliability=reliability,
        corroboration_count=1,
        days_since_seen=days_since,
        extraction_quality=extraction_quality,
    )
    score = compute_confidence(DataType.ARTICLE, confidence_inputs)

    text_for_tags = f"{title} {_strip_html(summary_html)}"
    auto_tags = _detect_tags(text_for_tags)
    # Merge feed-level curated tags (analyst-configured) with auto-detected
    # keyword tags. Feed tags always apply; auto tags add depth per article.
    feed_tags = list(getattr(feed, "tags", None) or [])
    tags = sorted(set(feed_tags) | set(auto_tags))
    truncated_content = (main_text[:50000] or None)
    content_hash = hashlib.sha256((truncated_content or "").encode("utf-8")).hexdigest()

    return {
        "id": uuid.uuid4(),
        "url_hash": _hash_url(url),
        "source_feed_id": feed.id,
        "source_name": source_name,
        "title": title.strip()[:1000],
        "url": url,
        "author": (entry.get("author") or None),
        "published_at": published_at,
        "summary": _strip_html(summary_html)[:4000] or None,
        "content_text": truncated_content,
        "content_hash": content_hash,
        "tags": tags,
        "confidence_score": score,
        "confidence_inputs": confidence_inputs.model_dump(),
    }


async def ingest_feed(
    *,
    feed: Feed,
    session: AsyncSession,
    user_agent: str,
    health: SourceHealthRepository,
) -> tuple[int, int]:
    """Pull one feed. Returns (articles_added, articles_seen)."""
    source = f"feed:{feed.name}"

    def factory():
        return build_resilient_client(timeout=None)

    result = await fetch_with_resilience(
        source, lambda: _fetch_feed_text(factory, feed.url, user_agent=user_agent), health=health
    )
    if not result.success or result.value is None:
        return 0, 0

    parsed = feedparser.parse(result.value)
    reliability = float(SOURCE_RELIABILITY.get(feed.name, feed.reliability))

    added = 0
    enriched = 0
    seen = len(parsed.entries)
    now = datetime.now(timezone.utc)
    for entry in parsed.entries:
        values = _build_article(
            entry=entry, feed=feed, source_name=feed.name, reliability=reliability
        )
        if values is None:
            continue

        # Look up existing row to decide between INSERT, ENRICH, and SKIP.
        existing = await session.scalar(
            select(Article).where(Article.url_hash == values["url_hash"])
        )

        if existing is None:
            await session.execute(
                insert(Article).values(**values, updated_at=now)
            )
            added += 1
            continue

        # Re-fetch path. Only update fields if the canonical content changed.
        if existing.content_hash == values["content_hash"]:
            # Content unchanged — touch fetched_at-like fields only and skip.
            continue

        await session.execute(
            Article.__table__.update()
            .where(Article.id == existing.id)
            .values(
                title=values["title"],
                summary=values["summary"],
                content_text=values["content_text"],
                content_hash=values["content_hash"],
                tags=values["tags"],
                confidence_score=values["confidence_score"],
                confidence_inputs=values["confidence_inputs"],
                published_at=values["published_at"] or existing.published_at,
                updated_at=now,
            )
        )
        # Invalidate any cached AI insight — content changed, must re-generate
        await session.execute(
            ArticleInsight.__table__.delete().where(
                ArticleInsight.article_id == existing.id
            )
        )
        enriched += 1
        logger.info(
            "article_enriched", article_id=str(existing.id), url=values["url"]
        )

    # The `feed` object was loaded by the outer session in run_ingestion_cycle()
    # and is detached from this inner session — assigning to .last_pulled_at would
    # be tracked by no transaction. Use an explicit UPDATE so it actually persists.
    await session.execute(
        Feed.__table__.update().where(Feed.id == feed.id).values(last_pulled_at=now)
    )
    await session.flush()
    logger.info("feed_ingest_done", feed=feed.name, added=added, enriched=enriched, seen=seen)
    return added, seen


async def run_ingestion_cycle(
    *,
    session_factory,
    user_agent: str,
    health: SourceHealthRepository,
    run_id: str,
) -> dict[str, Any]:
    async with session_factory() as session:
        feeds = (
            await session.execute(select(Feed).where(Feed.active.is_(True)))
        ).scalars().all()

    if not feeds:
        return {
            "run_id": run_id,
            "status": "success",
            "feeds_attempted": 0,
            "feeds_succeeded": 0,
            "articles_added": 0,
            "articles_seen": 0,
            "failed_sources": [],
        }

    async def _run_one(feed: Feed) -> tuple[Feed, int, int, str | None]:
        try:
            async with session_factory() as session:
                added, seen = await ingest_feed(
                    feed=feed,
                    session=session,
                    user_agent=user_agent,
                    health=health,
                )
                await session.commit()
                return feed, added, seen, None
        except Exception as e:
            logger.exception("feed_ingest_failed", feed=feed.name, error=str(e))
            return feed, 0, 0, str(e)

    results = await asyncio.gather(*(_run_one(f) for f in feeds), return_exceptions=False)

    total_added = sum(r[1] for r in results)
    total_seen = sum(r[2] for r in results)
    failed = [r[0].name for r in results if r[3] is not None]
    succeeded = len(results) - len(failed)

    return {
        "run_id": run_id,
        "status": "success",
        "feeds_attempted": len(results),
        "feeds_succeeded": succeeded,
        "articles_added": total_added,
        "articles_seen": total_seen,
        "failed_sources": failed,
    }
