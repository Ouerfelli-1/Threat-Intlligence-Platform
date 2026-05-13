import uuid
from datetime import date, datetime

from pydantic import BaseModel


class WazuhAlertOut(BaseModel):
    alert_id: str
    agent_id: str | None
    agent_name: str | None
    rule_id: str | None
    rule_description: str | None
    severity: int
    timestamp: datetime | None

    model_config = {"from_attributes": True}


class WazuhAgentOut(BaseModel):
    agent_id: str
    hostname: str | None
    ip: str | None
    os: str | None
    version: str | None
    last_seen: datetime | None
    status: str

    model_config = {"from_attributes": True}


class MISPEventOut(BaseModel):
    event_id: str
    info: str | None
    threat_level_id: int | None
    analysis: int | None
    date: date | None
    org: str | None

    model_config = {"from_attributes": True}


class MISPIocOut(BaseModel):
    id: uuid.UUID
    event_id: str
    type: str
    normalized_value: str
    raw_value: str
    comment: str | None
    to_ids: bool

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
