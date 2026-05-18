from tip_common import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "cmdb"
    service_port: int = 8007
    database_schema: str = "cmdb"
    asm_url: str = "http://asm:8009"


def get_settings() -> Settings:
    return Settings()
