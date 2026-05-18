from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = Field(..., description="Stable service identifier, e.g. 'news-collector'")
    service_port: int = Field(..., description="Port the service listens on")

    tip_env: Literal["development", "production"] = "development"
    log_level: str = "INFO"

    database_url: str = Field(
        default="postgresql+asyncpg://tip:tip@pgbouncer:6432/tip",
        description="Async Postgres URL (asyncpg through PgBouncer)",
    )
    database_schema: str = Field(..., description="Per-service Postgres schema name")
    redis_url: str = Field(default="redis://redis:6379/0")

    secrets_url: str = Field(default="http://secrets:8012")
    secrets_bootstrap_token: str = Field(default="")

    auth_url: str = Field(default="http://auth:8000")
    auth_public_key: str = Field(default="", description="RS256 public key (PEM); fetched if blank")
    disable_auth: bool = False

    # AI provider config — used by build_ai_client() in tip_ai.factory.
    # `litellm` (default): unified gateway, supports OpenAI / Anthropic / Groq /
    #                      Gemini / Mistral / Cohere / OpenRouter / etc. Picks
    #                      provider based on `ai_primary_model`.
    # `openrouter` (legacy): force the historical OpenRouter client.
    ai_provider: Literal["litellm", "openrouter"] = "litellm"
    ai_primary_model: str = Field(
        default="anthropic/claude-3-5-haiku-20241022",
        description="Primary model identifier (LiteLLM-format: '<provider>/<model>')",
    )
    ai_fallback_models: str = Field(
        default="",
        description=(
            "Comma-separated ordered list of fallback models. Empty defaults to "
            "[openrouter/<primary>] if OPENROUTER_API_KEY is set."
        ),
    )
    ai_openrouter_model: str = Field(
        default="anthropic/claude-3-5-haiku",
        description="Legacy: model used when ai_provider='openrouter'",
    )

    # LiteLLM proxy — the standalone gateway service that fronts every upstream
    # provider. Services POST OpenAI-format requests to this URL; the master key
    # comes from the secrets vault (LITELLM_MASTER_KEY) and is supplied to
    # build_ai_client() at startup, not via env var.
    litellm_proxy_url: str = Field(
        default="http://litellm:4000",
        description="Base URL of the LiteLLM proxy (e.g. http://litellm:4000)",
    )
