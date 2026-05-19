import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


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
    analyst_status: str = "unreviewed"

    model_config = {"from_attributes": True}


class ThreatList(BaseModel):
    items: list[ThreatOut]
    total: int


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
    analyst_override: dict | None = None

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


class AnalystStatusUpdate(BaseModel):
    analyst_status: str = Field(..., pattern=r"^(unreviewed|relevant|not_relevant|escalated|reviewed)$")


class InsightOverrideIn(BaseModel):
    analyst_override: dict


class AnalyzeRequest(BaseModel):
    actions: list[str] | None = None
    flowviz: bool = True
    model: str | None = None
    # When the threat already has a saved insight row at the current
    # PROMPT_VERSION, return it instead of re-running the AI. Set true to
    # force a fresh generation (the "Re-analyze" button does this).
    force: bool = False


class ThreatCreateManual(BaseModel):
    type: str = Field(..., pattern=r"^(supply_chain|data_breach|leak|disclosure|report)$")
    title: str = Field(..., min_length=1, max_length=512)
    summary: str | None = None
    severity: str = "medium"
    details: dict = Field(default_factory=dict)
