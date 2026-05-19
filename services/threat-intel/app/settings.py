from functools import lru_cache

from tip_common import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "threat-intel"
    service_port: int = 8003
    database_schema: str = "threat"

    cmdb_url: str = "http://cmdb:8007"
    orchestrator_url: str = "http://orchestrator:8014"
    # Flowviz is called inline by /threats/{id}/analyze to attach an attack-flow
    # to the insight payload (alongside hunting hypothesis + extracted IOCs).
    flowviz_url: str = "http://flowviz:8008"
    # IOC collector receives high-confidence extracted IOCs (auto-promotion).
    ioc_collector_url: str = "http://ioc-collector:8004"


@lru_cache
def get_settings() -> Settings:
    return Settings()
