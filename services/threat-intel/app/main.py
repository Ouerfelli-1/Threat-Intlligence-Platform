from fastapi import FastAPI

from tip_ai import build_ai_client
from tip_auth import JWTAuthMiddleware
from tip_cache import Cache
from tip_common import build_notes_router, create_service_app, wire_auth
from tip_secrets import SecretsClient
from tip_source_health import SourceHealthRepository

from app.db import close_engine, get_session, get_session_factory, init_engine
from app.models import SourceHealth, ThreatNote
from app.routes import health, ingest, threats
from app.settings import get_settings

settings = get_settings()


async def _startup(app: FastAPI) -> None:
    init_engine(settings)
    session_factory = get_session_factory()
    app.state.session_factory = session_factory
    app.state.settings = settings
    cache = Cache.from_url(settings.redis_url)
    app.state.cache = cache
    app.state.source_health = SourceHealthRepository(
        service=settings.service_name,
        table=SourceHealth,
        session_factory=session_factory,
        cache=cache,
    )
    secrets = SecretsClient(
        base_url=settings.secrets_url,
        service_name=settings.service_name,
        bootstrap_token=settings.secrets_bootstrap_token,
    )
    app.state.secrets = secrets
    try:
        app.state.hibp_api_key = await secrets.get_optional("HIBP_API_KEY")
    except Exception:
        app.state.hibp_api_key = None

    # Pull the LiteLLM proxy key + provider keys so threat-intel can run its
    # own AI passes (hunting-hypothesis + IOC extraction) instead of trampolining
    # through the orchestrator action queue. Same shape as vuln-intel.
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
    # Allow runtime override of primary/fallback models without redeploy
    primary_override = await secrets.get_optional("AI_PRIMARY_MODEL")
    if primary_override:
        settings.ai_primary_model = primary_override
    fallbacks_override = await secrets.get_optional("AI_FALLBACK_MODELS")
    if fallbacks_override is not None:
        settings.ai_fallback_models = fallbacks_override
    app.state.ai_client = build_ai_client(ai_secrets, settings)
    # Stash the secret bag so we can build a smarter-model client per request
    # (threat insight uses gpt-4o-class for richer hunting hypotheses).
    app.state.ai_secrets = ai_secrets

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
        try:
            await ai_client.close()
        except Exception:
            pass
    await close_engine()


app = create_service_app(
    settings=settings,
    title="TIP Threat Intel",
    description="Supply chain threats, HIBP breaches, public disclosures",
    on_startup=[_startup],
    on_shutdown=[_shutdown],
)
app.add_middleware(
    JWTAuthMiddleware,
    public_key=settings.auth_public_key,
    disable_auth=settings.disable_auth,
    tip_env=settings.tip_env,
)

threat_notes_router = build_notes_router(
    prefix="/threats",
    resource_id_param="threat_id",
    note_model=ThreatNote,
    resource_id_column="threat_id",
    perm_read="threats:read",
    perm_write="threats:write",
    get_session=get_session,
    tags=["threats"],
)

app.include_router(threats.router)
app.include_router(threat_notes_router)
app.include_router(ingest.router)
app.include_router(health.router)
