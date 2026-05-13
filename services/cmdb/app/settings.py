from tip_common import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "cmdb"
    service_port: int = 8007
    database_schema: str = "cmdb"


def get_settings() -> Settings:
    return Settings()
