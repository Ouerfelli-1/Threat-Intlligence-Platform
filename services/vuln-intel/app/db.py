from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from tip_db import SessionFactory, build_async_engine, build_session_factory

from app.settings import Settings

_engine: AsyncEngine | None = None
_session_factory: SessionFactory | None = None


def init_engine(settings: Settings) -> None:
    global _engine, _session_factory
    _engine = build_async_engine(settings.database_url)
    _session_factory = build_session_factory(_engine)


def get_session_factory() -> SessionFactory:
    if _session_factory is None:
        raise RuntimeError("session factory not initialized")
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_engine() -> None:
    if _engine is not None:
        await _engine.dispose()
