from tip_common import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "news-collector"
    service_port: int = 8001
    database_schema: str = "news"

    cmdb_url: str = "http://cmdb:8007"
    orchestrator_model: str = "anthropic/claude-haiku-4.5"
    user_agent: str = "TIP-NewsCollector/0.1 (+https://tip.local)"


def get_settings() -> Settings:
    return Settings()
