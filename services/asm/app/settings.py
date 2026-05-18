from functools import lru_cache

from tip_common import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "asm"
    service_port: int = 8009
    database_schema: str = "asm"
    scheduler_url: str = "http://scheduler:8011"


@lru_cache
def get_settings() -> Settings:
    return Settings()
