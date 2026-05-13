import uuid
from datetime import date, datetime

from pydantic import BaseModel


class ThreatOut(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    source: str
    source_url: str | None
    observed_at: datetime
    summary: str | None
    severity: str
    confidence_score: float

    model_config = {"from_attributes": True}


class HIBPBreachOut(BaseModel):
    name: str
    breach_date: date | None
    added_date: date | None
    pwn_count: int
    data_classes: list[str]
    description: str | None
    is_verified: bool
    is_sensitive: bool

    model_config = {"from_attributes": True}


class ThreatInsightOut(BaseModel):
    threat_id: uuid.UUID
    payload: dict
    model_name: str
    prompt_version: str
    generated_at: datetime

    model_config = {"from_attributes": True}


class SourceHealthOut(BaseModel):
    source_name: str
    last_success_at: datetime | None
    last_failure_at: datetime | None
    consecutive_failures: int
    status: str
    last_error: str | None
    last_http_status: int | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}
