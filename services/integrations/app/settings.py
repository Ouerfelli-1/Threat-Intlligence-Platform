from functools import lru_cache

from tip_common import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "integrations"
    service_port: int = 8006
    database_schema: str = "integrations"

    ioc_collector_url: str = "http://ioc-collector:8004"


@lru_cache
def get_settings() -> Settings:
    return Settings()
