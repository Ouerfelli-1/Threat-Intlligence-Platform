from tip_common import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "vuln-intel"
    service_port: int = 8002
    database_schema: str = "vuln"

    nvd_base_url: str = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    epss_url: str = "https://epss.cyentia.com/epss_scores-current.csv.gz"
    kev_url: str = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    orchestrator_url: str = "http://orchestrator:8014"
    cmdb_url: str = "http://cmdb:8007"
    user_agent: str = "TIP-VulnIntel/0.1"


def get_settings() -> Settings:
    return Settings()
