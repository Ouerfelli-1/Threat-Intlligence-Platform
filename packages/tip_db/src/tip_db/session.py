from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

SessionFactory = async_sessionmaker[AsyncSession]


def build_async_engine(url: str, *, echo: bool = False) -> AsyncEngine:
    # PgBouncer (transaction pooling) periodically closes idle backend
    # connections under the client; pool_pre_ping catches and rebuilds them
    # before they're handed to the app. pool_recycle bounds the max age of a
    # pooled connection so we never use one that's silently been killed
    # mid-idle (asyncpg caches "server_login_failed" errors briefly after
    # a bad reconnect — recycling avoids the cached-failure window).
    return create_async_engine(
        url,
        echo=echo,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=10,
        max_overflow=15,
        pool_timeout=20,
        connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    )


def build_session_factory(engine: AsyncEngine) -> SessionFactory:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_session(factory: SessionFactory) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
