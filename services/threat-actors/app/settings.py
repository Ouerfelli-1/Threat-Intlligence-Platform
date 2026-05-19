from functools import lru_cache

from tip_common import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "threat-actors"
    service_port: int = 8005
    database_schema: str = "actors"

    malpedia_api_token: str = ""
    orchestrator_url: str = "http://orchestrator:8014"
    scheduler_url: str = "http://scheduler:8011"
    flowviz_url: str = "http://flowviz:8008"
    ioc_collector_url: str = "http://ioc-collector:8004"


@lru_cache
def get_settings() -> Settings:
    return Settings()
