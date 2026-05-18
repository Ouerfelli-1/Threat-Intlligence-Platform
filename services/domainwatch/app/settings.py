from functools import lru_cache

from tip_common import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "domainwatch"
    service_port: int = 8010
    database_schema: str = "domainwatch"

    screenshot_dir: str = "/var/lib/domainwatch/screenshots"
    ioc_collector_url: str = "http://ioc-collector:8004"
    scheduler_url: str = "http://scheduler:8011"


@lru_cache
def get_settings() -> Settings:
    return Settings()
