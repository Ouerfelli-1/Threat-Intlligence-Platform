from functools import lru_cache

from tip_common import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "flowviz"
    service_port: int = 8008
    database_schema: str = "flowviz"

    flowviz_model: str = "anthropic/claude-sonnet-4.6"


@lru_cache
def get_settings() -> Settings:
    return Settings()
