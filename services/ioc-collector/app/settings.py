from tip_common import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "ioc-collector"
    service_port: int = 8004
    database_schema: str = "ioc"

    threatfox_url: str = "https://threatfox-api.abuse.ch/api/v1/"
    malbazaar_url: str = "https://mb-api.abuse.ch/api/v1/"
    otx_url: str = "https://otx.alienvault.com/api/v1/indicators/export"


def get_settings() -> Settings:
    return Settings()
