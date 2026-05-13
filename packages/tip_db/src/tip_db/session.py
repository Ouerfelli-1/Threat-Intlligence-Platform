from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

SessionFactory = async_sessionmaker[AsyncSession]


def build_async_engine(url: str, *, echo: bool = False) -> AsyncEngine:
    return create_async_engine(
        url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=10,
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
