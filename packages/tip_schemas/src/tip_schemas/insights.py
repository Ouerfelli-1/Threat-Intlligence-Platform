from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TTPFinding(BaseModel):
    technique_id: str = Field(..., description="MITRE ATT&CK technique ID, e.g. T1078")
    technique_name: str
    sub_technique_id: str | None = None
    tactic: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str | None = None


class ExtractedIOC(BaseModel):
    type: Literal["ip", "domain", "url", "md5", "sha1", "sha256", "email"]
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    context: str | None = None


class AttributedActor(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    basis: Literal["confirmed", "inferred"] = "inferred"
    evidence: list[str] = Field(default_factory=list)


class AIInsight(BaseModel):
    summary: str
    ttps: list[TTPFinding] = Field(default_factory=list)
    iocs: list[ExtractedIOC] = Field(default_factory=list)
    actor: AttributedActor | None = None
    relevance_to_us: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    recommended_actions: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    model_name: str | None = None
    prompt_version: str | None = None
    generated_at: datetime | None = None
