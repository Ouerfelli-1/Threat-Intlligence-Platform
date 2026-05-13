from tip_common import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "orchestrator"
    service_port: int = 8014
    database_schema: str = "orchestrator"

    vuln_intel_url: str = "http://vuln-intel:8002"
    threat_actors_url: str = "http://threat-actors:8005"
    integrations_url: str = "http://integrations:8006"
    cmdb_url: str = "http://cmdb:8007"
    flowviz_url: str = "http://flowviz:8008"
    ioc_collector_url: str = "http://ioc-collector:8004"
    news_collector_url: str = "http://news-collector:8001"

    orchestrator_model: str = "anthropic/claude-haiku-4.5"


def get_settings() -> Settings:
    return Settings()
