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
