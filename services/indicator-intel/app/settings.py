from tip_common import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "indicator-intel"
    service_port: int = 8013
    database_schema: str = "indicator"

    ioc_collector_url: str = "http://ioc-collector:8004"
    threat_actors_url: str = "http://threat-actors:8005"
    news_collector_url: str = "http://news-collector:8001"

    shodan_api_key: str = ""
    intelowl_url: str = ""
    intelowl_api_key: str = ""
    otx_api_key: str = ""
    abuseipdb_api_key: str = ""


def get_settings() -> Settings:
    return Settings()
