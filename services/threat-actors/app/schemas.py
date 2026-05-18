import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class ActorTTPOut(BaseModel):
    technique_id: str
    technique_name: str
    sub_technique_id: str | None
    confidence: float
    source: str

    model_config = {"from_attributes": True}


class ToolOut(BaseModel):
    id: uuid.UUID
    name: str
    aliases: list[str]
    type: str
    mitre_id: str | None
    description: str | None
    malpedia_url: str | None = None

    model_config = {"from_attributes": True}


class ActorOut(BaseModel):
    id: uuid.UUID
    mitre_id: str | None
    name: str
    aliases: list[str]
    origin_country: str | None
    description: str | None = None
    motivation: list[str]
    active_since: date | None
    last_seen: date | None
    target_sectors: list[str]
    target_countries: list[str]
    status: str
    analyst_status: str = "unreviewed"

    model_config = {"from_attributes": True}


class ActorList(BaseModel):
    items: list[ActorOut]
    total: int


class ActorDetailOut(ActorOut):
    ttps: list[ActorTTPOut] = []
    tools: list[ToolOut] = []
    # Linked ransomware groups (correlated by name/alias on the ingest path)
    ransomware_groups: list["RansomwareGroupOut"] = []


class RansomwareGroupOut(BaseModel):
    id: uuid.UUID
    name: str
    aliases: list[str]
    status: str
    first_seen: date | None
    last_seen: date | None
    variants: list[str]
    leak_site_url: str | None
    ransom_range: dict
    # Phase 4 enrichments
    description: str | None = None
    profile_url: str | None = None
    tor_urls: list[str] = []
    domains: list[str] = []
    locations: list[str] = []
    iocs: dict = {}
    victim_count: int = 0
    target_countries: list[str] = []
    target_sectors: list[str] = []
    actor_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class RansomwareGroupList(BaseModel):
    items: list[RansomwareGroupOut]
    total: int


class RansomwareVictimOut(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    group_name: str | None = None
    actor_id: uuid.UUID | None = None
    actor_name: str | None = None
    victim_name: str
    sector: str | None
    country: str | None
    disclosed_at: datetime | None
    source: str

    model_config = {"from_attributes": True}


class RansomwareVictimList(BaseModel):
    items: list[RansomwareVictimOut]
    total: int


class ActorInsightOut(BaseModel):
    actor_id: uuid.UUID
    payload: dict
    model_name: str
    prompt_version: str
    generated_at: datetime
    analyst_override: dict | None = None

    model_config = {"from_attributes": True}


class AnalystStatusUpdate(BaseModel):
    analyst_status: str = Field(..., pattern=r"^(unreviewed|relevant|not_relevant|escalated|reviewed)$")


class InsightOverrideIn(BaseModel):
    analyst_override: dict


class AnalyzeRequest(BaseModel):
    actions: list[str] | None = None
    flowviz: bool = True
    model: str | None = None


class ActorCreateManual(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    mitre_id: str | None = None
    aliases: list[str] = Field(default_factory=list)
    origin_country: str | None = None
    description: str | None = None
    motivation: list[str] = Field(default_factory=list)
    target_sectors: list[str] = Field(default_factory=list)
    target_countries: list[str] = Field(default_factory=list)


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


# Resolve forward refs (ActorDetailOut.ransomware_groups -> RansomwareGroupOut)
ActorDetailOut.model_rebuild()
