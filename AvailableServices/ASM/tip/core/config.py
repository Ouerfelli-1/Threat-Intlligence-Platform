"""
Central configuration for the Threat Intelligence Platform.
All settings are loaded from environment variables with sensible defaults.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Central configuration for all TIP modules."""

    # ── Application ──────────────────────────────────────────────
    APP_NAME: str = "Threat Intelligence Platform"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── TIP Database (separate from recon DB) ────────────────────
    TIP_DB_HOST: str = "localhost"
    TIP_DB_PORT: int = 5433
    TIP_DB_NAME: str = "tip_db"
    TIP_DB_USER: str = "tip_user"
    TIP_DB_PASSWORD: str = "tip_changeme"

    @property
    def TIP_DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.TIP_DB_USER}:{self.TIP_DB_PASSWORD}"
            f"@{self.TIP_DB_HOST}:{self.TIP_DB_PORT}/{self.TIP_DB_NAME}"
        )

    # ── Existing Recon Stack ─────────────────────────────────────
    RECON_FINDINGS_API_URL: str = "http://localhost:8001"
    RECON_MANAGER_API_URL: str = "http://localhost:8000"

    # ── Wazuh Integration ────────────────────────────────────────
    WAZUH_API_URL: str = "https://localhost:55000"
    WAZUH_API_USER: str = "wazuh-wui"
    WAZUH_API_PASSWORD: str = "changeme"
    WAZUH_VERIFY_SSL: bool = False

    # ── MISP Integration ─────────────────────────────────────────
    MISP_URL: str = "https://localhost:8443"
    MISP_API_KEY: str = ""
    MISP_VERIFY_SSL: bool = False

    # ── OpenCTI Integration ──────────────────────────────────────
    OPENCTI_URL: str = "http://localhost:8080"
    OPENCTI_API_KEY: str = ""

    # ── Vulnerability Intelligence ───────────────────────────────
    NVD_API_KEY: str = ""
    CVE_FETCH_DAYS: int = 7
    NVD_RATE_LIMIT: float = 6.0       # seconds between calls (0.6 with key)

    # ── Data Leak Module ─────────────────────────────────────────
    LEAK_API_URL: str = "http://localhost:8081"
    LEAK_CHECK_INTERVAL: int = 3600    # seconds

    # ── Scheduler Intervals (seconds) ────────────────────────────
    SCHEDULE_ASM_SYNC: int = 21600     # 6 hours
    SCHEDULE_CVE_FETCH: int = 43200    # 12 hours
    SCHEDULE_LEAK_CHECK: int = 3600    # 1 hour
    SCHEDULE_IDS_INGEST: int = 1800    # 30 minutes
    SCHEDULE_CORRELATION: int = 3600   # 1 hour

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
