from functools import lru_cache

from tip_common import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "scheduler"
    service_port: int = 8011
    database_schema: str = "scheduler"

    # APScheduler needs a sync psycopg2 URL (postgresql:// not postgresql+asyncpg://)
    scheduler_db_url: str = ""

    # Target service URLs
    news_collector_url: str = "http://news-collector:8001"
    vuln_intel_url: str = "http://vuln-intel:8002"
    threat_intel_url: str = "http://threat-intel:8003"
    ioc_collector_url: str = "http://ioc-collector:8004"
    threat_actors_url: str = "http://threat-actors:8005"
    integrations_url: str = "http://integrations:8006"
    asm_url: str = "http://asm:8009"
    domainwatch_url: str = "http://domainwatch:8010"
    orchestrator_url: str = "http://orchestrator:8014"

    @property
    def sync_db_url(self) -> str:
        if self.scheduler_db_url:
            return self.scheduler_db_url
        # Derive a sync URL from the async one (replace asyncpg driver)
        url = self.database_url
        return url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql://", "postgresql+psycopg2://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
