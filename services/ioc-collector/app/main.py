from fastapi import FastAPI

from tip_auth import JWTAuthMiddleware
from tip_cache import Cache
from tip_common import build_notes_router, create_service_app, wire_auth
from tip_secrets import SecretsClient
from tip_source_health import SourceHealthRepository

from app.db import close_engine, get_session, get_session_factory, init_engine
from app.models import IndicatorNote, SourceHealth
from app.routes import health, indicators, ingest
from app.settings import get_settings

settings = get_settings()


async def _startup(app: FastAPI) -> None:
    init_engine(settings)
    cache = Cache.from_url(settings.redis_url)
    app.state.cache = cache
    app.state.source_health = SourceHealthRepository(
        service=settings.service_name,
        table=SourceHealth,
        session_factory=get_session_factory(),
        cache=cache,
    )
    secrets = SecretsClient(
        base_url=settings.secrets_url,
        service_name=settings.service_name,
        bootstrap_token=settings.secrets_bootstrap_token,
    )
    app.state.secrets = secrets
    try:
        app.state.abusech_api_key = await secrets.get_optional("ABUSECH_API_KEY")
    except Exception:
        app.state.abusech_api_key = None
    await wire_auth(app, settings, settings.service_name)
    jwt = getattr(app.state, "service_jwt", None)
    if jwt:
        secrets.set_service_jwt(jwt)


async def _shutdown(app: FastAPI) -> None:
    cache: Cache | None = getattr(app.state, "cache", None)
    if cache is not None:
        await cache.close()
    secrets: SecretsClient | None = getattr(app.state, "secrets", None)
    if secrets is not None:
        await secrets.close()
    await close_engine()


app = create_service_app(
    settings=settings,
    title="TIP IOC Collector",
    description="IOC ingestion + bulk lookup",
    on_startup=[_startup],
    on_shutdown=[_shutdown],
)
app.add_middleware(
    JWTAuthMiddleware,
    public_key=settings.auth_public_key,
    disable_auth=settings.disable_auth,
    tip_env=settings.tip_env,
)

indicator_notes_router = build_notes_router(
    prefix="/indicators",
    resource_id_param="indicator_id",
    note_model=IndicatorNote,
    resource_id_column="indicator_id",
    perm_read="iocs:read",
    perm_write="iocs:write",
    get_session=get_session,
    tags=["indicators"],
)

app.include_router(indicators.router)
app.include_router(indicator_notes_router)
app.include_router(ingest.router)
app.include_router(health.router)
