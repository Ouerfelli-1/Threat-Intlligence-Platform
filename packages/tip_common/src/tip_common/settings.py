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
