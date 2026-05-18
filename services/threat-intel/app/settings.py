from functools import lru_cache

from tip_common import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "threat-intel"
    service_port: int = 8003
    database_schema: str = "threat"

    cmdb_url: str = "http://cmdb:8007"
    orchestrator_url: str = "http://orchestrator:8014"


@lru_cache
def get_settings() -> Settings:
    return Settings()
