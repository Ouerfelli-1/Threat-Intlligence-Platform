from fastapi import FastAPI

from tip_ai import build_ai_client
from tip_auth import JWTAuthMiddleware
from tip_cache import Cache
from tip_common import build_notes_router, create_service_app, wire_auth
from tip_secrets import SecretNotFound, SecretsClient
from tip_source_health import SourceHealthRepository

from app.db import close_engine, get_session, get_session_factory, init_engine
from app.models import CVENote, SourceHealth
from app.routes import cves, health, refresh
from app.settings import get_settings

settings = get_settings()


async def _startup(app: FastAPI) -> None:
    init_engine(settings)
    app.state.settings = settings
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
        app.state.nvd_api_key = await secrets.get_optional("NVD_API_KEY")
    except Exception:
        app.state.nvd_api_key = None

    # AI client for the per-CVE insight endpoint (POST /cves/{id}/analyze).
    # Pulls LITELLM_MASTER_KEY + provider keys from the vault; talks to the
    # standalone proxy at settings.litellm_proxy_url.
    ai_secrets: dict[str, str] = {}
    for k in (
        "LITELLM_MASTER_KEY",
        "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "GROQ_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY",
        "COHERE_API_KEY", "TOGETHER_API_KEY", "DEEPSEEK_API_KEY",
        "GITHUB_API_KEY",
    ):
        try:
            ai_secrets[k] = await secrets.get_optional(k) or ""
        except Exception:
            ai_secrets[k] = ""

    # Honor the vault-level AI_PRIMARY_MODEL / AI_FALLBACK_MODELS overrides so
    # operators can swap models from the Settings UI without redeploying. The
    # other AI-consuming services (orchestrator, flowviz, indicator-intel) do
    # the same — keep this in sync.
    primary_override = await secrets.get_optional("AI_PRIMARY_MODEL")
    if primary_override:
        settings.ai_primary_model = primary_override
    fallbacks_override = await secrets.get_optional("AI_FALLBACK_MODELS")
    if fallbacks_override is not None:
        settings.ai_fallback_models = fallbacks_override

    app.state.ai_client = build_ai_client(ai_secrets, settings)

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
    ai_client = getattr(app.state, "ai_client", None)
    if ai_client is not None:
        await ai_client.close()
    await close_engine()


app = create_service_app(
    settings=settings,
    title="TIP Vulnerability Intelligence",
    description="CVE/EPSS/KEV ingestion + query",
    on_startup=[_startup],
    on_shutdown=[_shutdown],
)
app.add_middleware(
    JWTAuthMiddleware,
    public_key=settings.auth_public_key,
    disable_auth=settings.disable_auth,
    tip_env=settings.tip_env,
)

cve_notes_router = build_notes_router(
    prefix="/cves",
    resource_id_param="cve_id",
    note_model=CVENote,
    resource_id_column="cve_id",
    perm_read="intelligence:read",
    perm_write="intelligence:write",
    get_session=get_session,
    tags=["cves"],
)

app.include_router(cves.router)
app.include_router(cve_notes_router)
app.include_router(refresh.router)
app.include_router(health.router)
