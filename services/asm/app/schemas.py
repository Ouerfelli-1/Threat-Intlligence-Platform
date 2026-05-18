import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ScopeCreate(BaseModel):
    name: str
    description: str | None = None
    config: dict[str, Any] = {}


class ScopeOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    config: dict
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TargetCreate(BaseModel):
    scope_id: uuid.UUID
    type: str
    value: str
    description: str | None = None
    active: bool = True


class TargetUpdate(BaseModel):
    """Partial update for a target — currently used to toggle `active`."""
    active: bool | None = None
    description: str | None = None


class ScopeUpdate(BaseModel):
    """Partial update for a scope — `active` is the pause toggle."""
    name: str | None = None
    description: str | None = None
    config: dict[str, Any] | None = None
    active: bool | None = None


class TargetOut(BaseModel):
    id: uuid.UUID
    scope_id: uuid.UUID
    type: str
    value: str
    description: str | None
    active: bool
    added_at: datetime

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: uuid.UUID
    scope_id: uuid.UUID | None
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    findings_count: int
    error: str | None

    model_config = {"from_attributes": True}


class FindingOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    target_id: uuid.UUID | None
    type: str
    value: str
    source: str
    discovered_at: datetime
    details: dict

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
