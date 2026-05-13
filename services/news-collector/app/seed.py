from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Feed
from app.sources import DEFAULT_FEEDS


async def seed_feeds_if_empty(session: AsyncSession) -> int:
    existing = (await session.execute(select(func.count()).select_from(Feed))).scalar_one()
    if existing > 0:
        return 0
    for seed in DEFAULT_FEEDS:
        session.add(
            Feed(name=seed.name, url=seed.url, reliability=seed.reliability, kind="rss", active=True)
        )
    await session.commit()
    return len(DEFAULT_FEEDS)
