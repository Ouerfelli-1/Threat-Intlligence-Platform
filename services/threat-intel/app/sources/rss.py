"""
Pulls supply-chain / threat intelligence RSS feeds and stores normalized Threat rows.
"""
import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_http import build_resilient_client
from tip_schemas.confidence import ConfidenceInputs, DataType, compute_confidence
from tip_source_health import SourceHealthRepository

from app.models import Threat

log = logging.getLogger(__name__)

_TAG_PATTERNS = {
    "supply_chain": ["supply chain", "dependency", "npm", "pypi", "package", "software bill"],
    "data_breach": ["breach", "data leak", "leaked", "stolen data", "exposed data"],
    "ransomware": ["ransomware", "ransom"],
    "disclosure": ["disclosure", "advisory", "cve-", "vulnerability"],
}


def _detect_type(text: str) -> str:
    lower = text.lower()
    for threat_type, keywords in _TAG_PATTERNS.items():
        if any(kw in lower for kw in keywords):
            return threat_type
    return "disclosure"


def _detect_severity(text: str) -> str:
    lower = text.lower()
    if any(w in lower for w in ["critical", "actively exploited", "zero-day", "zero day"]):
        return "critical"
    if any(w in lower for w in ["high", "severe"]):
        return "high"
    if any(w in lower for w in ["medium", "moderate"]):
        return "medium"
    return "low"


def _parse_pub_date(entry: dict) -> datetime:
    for field in ("published", "updated"):
        val = entry.get(f"{field}_parsed") or entry.get(field)
        if val:
            try:
                if hasattr(val, "tm_year"):
                    import time
                    return datetime(*val[:6], tzinfo=timezone.utc)
                return parsedate_to_datetime(str(val)).astimezone(timezone.utc)
            except Exception:
                continue
    return datetime.now(timezone.utc)


async def ingest_feed(session: AsyncSession, feed_config: dict, health: SourceHealthRepository) -> int:
    source_name = feed_config["name"]
    url = feed_config["url"]
    reliability = feed_config["reliability"]

    # is_open() == True means circuit breaker is open → SKIP the source.
    if await health.is_open(source_name):
        log.info("feed_skipped source=%s circuit_open=True", source_name)
        return 0

    try:
        async with build_resilient_client() as client:
            resp = await client.get(url, timeout=30)
            resp.raise_for_status()
            content = resp.content
    except Exception as exc:
        log.error("feed_fetch_failed source=%s error=%s", source_name, exc)
        await health.mark_failure(source_name, str(exc))
        return 0

    feed = feedparser.parse(content)
    count = 0

    enriched = 0
    for entry in feed.entries:
        url_hash = hashlib.sha256((entry.get("link", "") or entry.get("id", "")).encode()).hexdigest()
        title = entry.get("title", "")
        summary = entry.get("summary", entry.get("description", ""))
        observed_at = _parse_pub_date(entry)
        content_hash = hashlib.sha256(f"{title}|{summary}".encode("utf-8")).hexdigest()

        existing_q = await session.execute(
            select(Threat).where(Threat.details["url_hash"].astext == url_hash)
        )
        existing = existing_q.scalar_one_or_none()

        days_since = max(0.0, (datetime.now(timezone.utc) - observed_at).total_seconds() / 86400.0)
        conf_inputs = ConfidenceInputs(
            source_reliability=reliability,
            corroboration_count=1,
            days_since_seen=days_since,
            extraction_quality=0.8,
        )
        confidence_score = compute_confidence(DataType.ARTICLE, conf_inputs)

        if existing is not None:
            stored_hash = (existing.details or {}).get("content_hash")
            if stored_hash == content_hash:
                continue  # unchanged
            # ENRICH: title/summary/severity may have been updated upstream
            existing.title = title[:512]
            existing.summary = summary[:2048] if summary else None
            existing.severity = _detect_severity(f"{title} {summary}")
            existing.type = _detect_type(f"{title} {summary}")
            existing.confidence_score = confidence_score
            existing.confidence_inputs = conf_inputs.model_dump()
            existing.details = {
                "url_hash": url_hash,
                "content_hash": content_hash,
                "raw_entry": {k: str(v) for k, v in entry.items() if isinstance(v, (str, int, float, bool))},
            }
            enriched += 1
            continue

        threat = Threat(
            id=uuid.uuid4(),
            type=_detect_type(f"{title} {summary}"),
            title=title[:512],
            source=source_name,
            source_url=entry.get("link"),
            observed_at=observed_at,
            summary=summary[:2048] if summary else None,
            severity=_detect_severity(f"{title} {summary}"),
            details={
                "url_hash": url_hash,
                "content_hash": content_hash,
                "raw_entry": {k: str(v) for k, v in entry.items() if isinstance(v, (str, int, float, bool))},
            },
            confidence_score=confidence_score,
            confidence_inputs=conf_inputs.model_dump(),
        )
        session.add(threat)
        count += 1

    try:
        await session.commit()
        await health.mark_success(source_name)
        log.info("feed_ingested source=%s added=%d enriched=%d", source_name, count, enriched)
    except Exception as exc:
        await session.rollback()
        await health.mark_failure(source_name, str(exc))
        log.error("feed_commit_failed source=%s error=%s", source_name, exc)
        return 0

    # Emit threat.supply_chain notifications post-commit. We only fire
    # for newly-added rows whose detected type is supply_chain (the
    # severity ladder + notification filter handles severity_min /
    # product_match in the dispatcher).
    if count:
        # Re-query to grab the newly-inserted supply_chain rows we just
        # committed. Cheaper than tracking refs in-loop because most
        # cycles return 0-3 new threats.
        new_sc_stmt = (
            select(Threat)
            .where(Threat.source == source_name, Threat.type == "supply_chain")
            .order_by(Threat.observed_at.desc())
            .limit(20)
        )
        new_sc = (await session.execute(new_sc_stmt)).scalars().all()
        # Filter to ones added in this cycle (last 5 min) so we don't
        # re-fire for everything in the table.
        from datetime import timedelta
        recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        for t in new_sc:
            if t.observed_at and t.observed_at >= recent_cutoff:
                await _notify_supply_chain(t)

    return count


async def _notify_supply_chain(threat) -> None:
    """Fire-and-forget POST to orchestrator /internal/notify for a new
    supply-chain threat row. Inter-service calls are unauthenticated."""
    orch_url = os.environ.get("ORCHESTRATOR_URL") or "http://orchestrator:8014"
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(
                f"{orch_url}/internal/notify",
                json={
                    "event_type": "threat.supply_chain",
                    "event_ref": str(threat.id),
                    "payload": {
                        "title": threat.title,
                        "summary": threat.summary or "",
                        "source": threat.source,
                        "source_url": threat.source_url,
                        "severity": threat.severity or "medium",
                        "link": f"/intelligence/supply-chain?id={threat.id}",
                    },
                },
            )
    except Exception as exc:
        log.warning("supply_chain_notify_failed threat=%s err=%s", threat.id, exc)
