from fastapi import FastAPI

from tip_auth import JWTAuthMiddleware
from tip_cache import Cache
from tip_common import create_service_app, wire_auth

from app.db import close_engine, get_session_factory, init_engine
from app.jobs import build_scheduler
from app.routes import scheduler
from app.settings import get_settings

settings = get_settings()


async def _startup(app: FastAPI) -> None:
    init_engine(settings)
    session_factory = get_session_factory()
    app.state.session_factory = session_factory
    cache = Cache.from_url(settings.redis_url)
    app.state.cache = cache

    aps = build_scheduler(settings, session_factory)
    aps.start()
    app.state.scheduler = aps
    await wire_auth(app, settings, settings.service_name)


async def _shutdown(app: FastAPI) -> None:
    aps = getattr(app.state, "scheduler", None)
    if aps is not None:
        aps.shutdown(wait=False)
    cache: Cache | None = getattr(app.state, "cache", None)
    if cache is not None:
        await cache.close()
    await close_engine()


app = create_service_app(
    settings=settings,
    title="TIP Scheduler",
    description="Central job scheduler — fires HTTP triggers to all platform services",
    on_startup=[_startup],
    on_shutdown=[_shutdown],
)
app.add_middleware(
    JWTAuthMiddleware,
    public_key=settings.auth_public_key,
    disable_auth=settings.disable_auth,
    tip_env=settings.tip_env,
)

app.include_router(scheduler.router)
