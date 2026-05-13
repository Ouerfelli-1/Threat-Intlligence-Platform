from fastapi import FastAPI

from tip_ai import OpenRouterClient
from tip_auth import JWTAuthMiddleware
from tip_cache import Cache
from tip_common import create_service_app, wire_auth
from tip_secrets import SecretsClient
from tip_source_health import SourceHealthRepository

from app.db import close_engine, get_session_factory, init_engine
from app.models import SourceHealth
from app.routes import analyze, health
from app.settings import get_settings

settings = get_settings()


async def _startup(app: FastAPI) -> None:
    init_engine(settings)
    cache = Cache.from_url(settings.redis_url)
    app.state.cache = cache
    app.state.settings = settings

    secrets = SecretsClient(
        base_url=settings.secrets_url,
        service_name=settings.service_name,
        bootstrap_token=settings.secrets_bootstrap_token,
    )
    openrouter_key = await secrets.get("OPENROUTER_API_KEY")
    await secrets.close()

    app.state.ai_client = OpenRouterClient(
        api_key=openrouter_key,
        model=settings.orchestrator_model,
    )

    app.state.source_health = SourceHealthRepository(
        service=settings.service_name,
        table=SourceHealth,
        session_factory=get_session_factory(),
        cache=cache,
    )
    await wire_auth(app, settings, settings.service_name)


async def _shutdown(app: FastAPI) -> None:
    cache: Cache | None = getattr(app.state, "cache", None)
    if cache is not None:
        await cache.close()
    await close_engine()


app = create_service_app(
    settings=settings,
    title="TIP Orchestrator",
    description="AI intelligence synthesis — CVE relevance, actor likelihood, correlations, executive briefs",
    on_startup=[_startup],
    on_shutdown=[_shutdown],
)
app.add_middleware(
    JWTAuthMiddleware,
    public_key=settings.auth_public_key,
    disable_auth=settings.disable_auth,
    tip_env=settings.tip_env,
)

app.include_router(analyze.router)
app.include_router(health.router)
