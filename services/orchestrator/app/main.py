from fastapi import FastAPI

from tip_ai import build_ai_client
from tip_auth import JWTAuthMiddleware
from tip_cache import Cache
from tip_common import create_service_app, wire_auth
from tip_secrets import SecretsClient
from tip_source_health import SourceHealthRepository

from app.db import close_engine, get_session_factory, init_engine
from app.models import SourceHealth
from app.routes import actions, analyze, health, policies
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
    # LITELLM_MASTER_KEY is what build_ai_client needs by default — the
    # standalone proxy validates it on every request. Provider keys remain
    # for the legacy ai_provider=openrouter path; missing keys are harmless.
    ai_secrets: dict[str, str] = {}
    for k in (
        "LITELLM_MASTER_KEY",
        "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "GROQ_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY",
        "COHERE_API_KEY", "TOGETHER_API_KEY", "DEEPSEEK_API_KEY",
        "GITHUB_API_KEY",
    ):
        try:
            ai_secrets[k] = await secrets.get(k)
        except Exception:
            ai_secrets[k] = ""

    # Allow admins to override AI_PRIMARY_MODEL / AI_FALLBACK_MODELS from the
    # secrets vault (Settings → AI providers) without an env-var/redeploy.
    primary_override = await secrets.get_optional("AI_PRIMARY_MODEL")
    if primary_override:
        settings.ai_primary_model = primary_override
    fallbacks_override = await secrets.get_optional("AI_FALLBACK_MODELS")
    if fallbacks_override is not None:
        settings.ai_fallback_models = fallbacks_override

    await secrets.close()
    app.state.ai_client = build_ai_client(ai_secrets, settings)

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
app.include_router(policies.router)
app.include_router(actions.router)
app.include_router(health.router)
