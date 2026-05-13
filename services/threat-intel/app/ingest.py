import asyncio
import logging

from tip_source_health import SourceHealthRepository

from app.sources import SUPPLY_CHAIN_FEEDS
from app.sources.hibp import sync_hibp
from app.sources.rss import ingest_feed

log = logging.getLogger(__name__)


async def run_ingestion_cycle(
    session_factory,
    health: SourceHealthRepository,
    hibp_api_key: str,
    cmdb_url: str,
    service_headers: dict,
) -> dict:
    results = {}

    async def _ingest_feed(feed_config: dict) -> int:
        async with session_factory() as session:
            return await ingest_feed(session, feed_config, health)

    feed_tasks = [_ingest_feed(f) for f in SUPPLY_CHAIN_FEEDS]
    feed_counts = await asyncio.gather(*feed_tasks, return_exceptions=True)
    for feed, count in zip(SUPPLY_CHAIN_FEEDS, feed_counts):
        results[feed["name"]] = count if isinstance(count, int) else 0

    async with session_factory() as session:
        results["hibp"] = await sync_hibp(
            session, health, hibp_api_key, cmdb_url, service_headers
        )

    log.info("threat_intel cycle complete results=%s", results)
    return results
