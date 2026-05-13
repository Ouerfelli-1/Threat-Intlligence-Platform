from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class InvestigateRequest(BaseModel):
    type: str  # "ip" | "domain"
    value: str


class AsyncInvestigateResponse(BaseModel):
    job_id: UUID
    status: str = "running"


class InvestigationOut(BaseModel):
    id: UUID
    indicator_type: str
    normalized_value: str
    raw_value: str
    status: str
    verdict: Optional[str]
    confidence: Optional[Decimal]
    risk_score: Optional[int]
    summary: Optional[str]
    payload: dict
    model_name: Optional[str]
    investigated_at: datetime
    duration_ms: Optional[int]

    model_config = {"from_attributes": True}
