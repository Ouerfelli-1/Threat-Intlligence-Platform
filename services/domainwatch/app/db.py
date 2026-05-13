from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import sessionmaker

from tip_db import build_async_engine, build_session_factory

from app.settings import get_settings

_engine: AsyncEngine | None = None
_session_factory: sessionmaker | None = None


def init_engine(settings=None) -> None:
    global _engine, _session_factory
    if settings is None:
        settings = get_settings()
    _engine = build_async_engine(settings.database_url)
    _session_factory = build_session_factory(_engine)


def get_session_factory() -> sessionmaker:
    assert _session_factory is not None, "Engine not initialized"
    return _session_factory


async def close_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
