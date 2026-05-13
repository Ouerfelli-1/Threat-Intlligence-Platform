from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class DataType(StrEnum):
    IOC = "ioc"
    CVE_RELEVANCE = "cve_relevance"
    ARTICLE = "article"
    ACTOR_ATTRIBUTION = "actor_attribution"
    TTP_MAPPING = "ttp_mapping"


class ConfidenceConfig(BaseModel):
    weights_version: str = "v1"
    w_source: float
    w_corroboration: float
    w_freshness: float
    w_extraction: float


CONFIGS: dict[DataType, ConfidenceConfig] = {
    DataType.IOC: ConfidenceConfig(w_source=0.4, w_corroboration=0.3, w_freshness=0.2, w_extraction=0.1),
    DataType.CVE_RELEVANCE: ConfidenceConfig(w_source=0.3, w_corroboration=0.1, w_freshness=0.3, w_extraction=0.3),
    DataType.ARTICLE: ConfidenceConfig(w_source=0.5, w_corroboration=0.1, w_freshness=0.3, w_extraction=0.1),
    DataType.ACTOR_ATTRIBUTION: ConfidenceConfig(w_source=0.4, w_corroboration=0.4, w_freshness=0.1, w_extraction=0.1),
    DataType.TTP_MAPPING: ConfidenceConfig(w_source=0.5, w_corroboration=0.2, w_freshness=0.1, w_extraction=0.2),
}


SOURCE_RELIABILITY: dict[str, float] = {
    "threatfox": 0.90,
    "malwarebazaar": 0.85,
    "otx": 0.70,
    "misp": 0.85,
    "cisa-kev": 0.98,
    "cisa-advisories": 0.95,
    "nvd": 0.95,
    "epss": 0.95,
    "mitre-attack": 0.98,
    "ransomware.live": 0.85,
    "malpedia": 0.85,
    "vx-underground": 0.40,
    "hibp": 0.95,
    "hackernews": 0.70,
    "malwarebytes": 0.80,
    "tenable": 0.85,
    "recordedfuture": 0.85,
    "stepsecurity": 0.75,
    "shodan": 0.85,
    "crtsh": 0.90,
    "ip-api": 0.75,
    "intelowl": 0.85,
    "awesome-ti": 0.75,
    "wazuh": 0.90,
    "rss-generic": 0.60,
}


class ConfidenceInputs(BaseModel):
    source_reliability: float = Field(ge=0.0, le=1.0)
    corroboration_count: int = Field(ge=0)
    days_since_seen: float = Field(ge=0.0)
    extraction_quality: float = Field(ge=0.0, le=1.0)
    weights_version: str = "v1"


def compute_confidence(data_type: DataType | str, inputs: ConfidenceInputs) -> float:
    cfg = CONFIGS[DataType(data_type)]
    freshness = max(0.0, 1.0 - inputs.days_since_seen / 30.0)
    corroboration = min(inputs.corroboration_count / 3.0, 1.0)
    score = (
        cfg.w_source * inputs.source_reliability
        + cfg.w_corroboration * corroboration
        + cfg.w_freshness * freshness
        + cfg.w_extraction * inputs.extraction_quality
    )
    return round(min(max(score, 0.0), 1.0), 2)


def days_between(now: datetime, earlier: datetime) -> float:
    if earlier.tzinfo is None:
        earlier = earlier.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return max(0.0, (now - earlier).total_seconds() / 86400.0)
