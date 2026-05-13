from functools import lru_cache

from pydantic import Field

from tip_common import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "secrets"
    service_port: int = 8012
    database_schema: str = "secrets"

    fernet_key: str = Field(..., description="Base64-encoded Fernet key (required)")
    secrets_bootstrap_token: str = Field("", description="Shared bootstrap token for pre-JWT access")


@lru_cache
def get_settings() -> Settings:
    return Settings()
