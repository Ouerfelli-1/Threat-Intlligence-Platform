from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Feed
from app.sources import DEFAULT_FEEDS

# Map feed name → correct URL for feeds whose URLs have changed.
# Applied on every startup so stale rows in existing deployments are healed.
_URL_CORRECTIONS: dict[str, str] = {
    "cisa-advisories": "https://www.cisa.gov/cybersecurity-advisories/all.xml",
    # CISA moved their ICS feed under /cybersecurity-advisories/ (old /ics-advisories/all.xml is 404)
    "cisa-ics":        "https://www.cisa.gov/cybersecurity-advisories/ics-advisories.xml",
    # /feed on recordedfuture.com is the corporate blog (low cadence). The actual
    # news daily-cadence feed is therecord.media/feed (Recorded Future News).
    "recordedfuture":  "https://therecord.media/feed/",
}


async def seed_feeds_if_empty(session: AsyncSession) -> int:
    existing = (await session.execute(select(func.count()).select_from(Feed))).scalar_one()
    if existing > 0:
        # Heal any known-broken feed URLs even when feeds already exist.
        await _repair_feed_urls(session)
        return 0
    for seed in DEFAULT_FEEDS:
        session.add(
            Feed(name=seed.name, url=seed.url, reliability=seed.reliability, kind="rss", active=True)
        )
    await session.commit()
    return len(DEFAULT_FEEDS)


async def _repair_feed_urls(session: AsyncSession) -> None:
    """Update feed URLs that have changed from their original seeded values."""
    changed = False
    for name, correct_url in _URL_CORRECTIONS.items():
        result = await session.execute(select(Feed).where(Feed.name == name))
        feed = result.scalar_one_or_none()
        if feed and feed.url != correct_url:
            feed.url = correct_url
            changed = True
    if changed:
        await session.commit()
