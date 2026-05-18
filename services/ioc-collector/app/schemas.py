import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IndicatorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    type: str
    normalized_value: str
    raw_value: str
    first_seen: datetime
    last_seen: datetime
    tags: list[str]
    confidence_score: float
    analyst_status: str = "unreviewed"


class IndicatorWithSources(IndicatorOut):
    sources: list[dict] = Field(default_factory=list)


class IndicatorList(BaseModel):
    items: list[IndicatorOut]
    total: int


class LookupRequest(BaseModel):
    indicators: list[dict[str, str]]   # [{"type": "ip", "value": "..."}]


class LookupHit(BaseModel):
    type: str
    value: str
    normalized_value: str
    found: bool
    indicator: IndicatorOut | None = None


class LookupResponse(BaseModel):
    hits: list[LookupHit]


class IngestResult(BaseModel):
    run_id: str
    status: str
    sources_attempted: int
    sources_succeeded: int
    indicators_added: int
    indicators_updated: int
    failed_sources: list[str]


class AnalystStatusUpdate(BaseModel):
    analyst_status: str = Field(..., pattern=r"^(unreviewed|relevant|not_relevant|escalated|reviewed)$")


class AnalyzeRequest(BaseModel):
    actions: list[str] | None = None
    flowviz: bool = False
    model: str | None = None


class IndicatorCreateManual(BaseModel):
    type: str = Field(..., pattern=r"^(ip|domain|url|sha256|sha1|md5)$")
    value: str = Field(..., min_length=1)
    malware_family: str | None = None
    threat_type: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None
