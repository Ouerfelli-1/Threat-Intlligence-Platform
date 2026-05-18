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


# ── AI Policies ──────────────────────────────────────────────────────────────

class PolicyCreate(BaseModel):
    scope: str  # global | category | resource
    category: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    mode: str  # full_auto | category_auto | on_demand
    actions: list[str] = []
    cmdb_filter: bool = False
    priority: int = 100
    active: bool = True


class PolicyUpdate(BaseModel):
    mode: Optional[str] = None
    actions: Optional[list[str]] = None
    cmdb_filter: Optional[bool] = None
    priority: Optional[int] = None
    active: Optional[bool] = None


class PolicyOut(BaseModel):
    id: UUID
    scope: str
    category: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    mode: str
    actions: list[str]
    cmdb_filter: bool
    priority: int
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PolicyDecisionOut(BaseModel):
    mode: str
    actions: list[str]
    cmdb_filter: bool
    policy_id: Optional[str] = None
    scope: str


# ── Action Runs ──────────────────────────────────────────────────────────────

class ActionRunRequest(BaseModel):
    resource_type: str
    resource_id: str
    actions: list[str]
    model: Optional[str] = None


class ActionRunOut(BaseModel):
    id: UUID
    resource_type: str
    resource_id: str
    action: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    output: Optional[dict] = None

    model_config = {"from_attributes": True}
