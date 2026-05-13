from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ReportOut(BaseModel):
    id: UUID
    kind: str
    payload: dict
    model_name: Optional[str]
    prompt_version: Optional[str]
    generated_at: datetime

    model_config = {"from_attributes": True}


class CveRelevanceOut(BaseModel):
    cve_id: str
    relevance_score: Decimal
    rationale: Optional[str]
    scored_at: datetime

    model_config = {"from_attributes": True}


class ActorLikelihoodOut(BaseModel):
    actor_id: UUID
    likelihood_score: Decimal
    ttps_overlap: list[str]
    rationale: Optional[str]
    scored_at: datetime

    model_config = {"from_attributes": True}


class CorrelationOut(BaseModel):
    id: UUID
    kind: str
    payload: dict
    detected_at: datetime

    model_config = {"from_attributes": True}


class AskRequest(BaseModel):
    question: str
    cve_id: Optional[str] = None
    ioc: Optional[str] = None
    actor: Optional[str] = None
    text: Optional[str] = None


class AnalysisJobResponse(BaseModel):
    run_id: UUID
    status: str = "running"
