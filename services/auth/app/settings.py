from tip_common import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "auth"
    service_port: int = 8000
    database_schema: str = "auth"

    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "changeme"


def get_settings() -> Settings:
    return Settings()
