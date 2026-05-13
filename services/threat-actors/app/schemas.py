import uuid
from datetime import date, datetime

from pydantic import BaseModel


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

    model_config = {"from_attributes": True}


class ActorOut(BaseModel):
    id: uuid.UUID
    mitre_id: str | None
    name: str
    aliases: list[str]
    origin_country: str | None
    motivation: list[str]
    active_since: date | None
    last_seen: date | None
    target_sectors: list[str]
    target_countries: list[str]
    status: str

    model_config = {"from_attributes": True}


class ActorDetailOut(ActorOut):
    ttps: list[ActorTTPOut] = []
    tools: list[ToolOut] = []


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

    model_config = {"from_attributes": True}


class RansomwareVictimOut(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    victim_name: str
    sector: str | None
    country: str | None
    disclosed_at: datetime | None
    source: str

    model_config = {"from_attributes": True}


class ActorInsightOut(BaseModel):
    actor_id: uuid.UUID
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
