import uuid
from datetime import datetime

from pydantic import BaseModel


class DomainCreate(BaseModel):
    name: str


class DomainOut(BaseModel):
    id: uuid.UUID
    name: str
    active: bool
    added_at: datetime
    last_checked_at: datetime | None

    model_config = {"from_attributes": True}


class SnapshotOut(BaseModel):
    id: uuid.UUID
    domain_id: uuid.UUID
    captured_at: datetime
    details: dict
    content_hash: str | None
    screenshot_path: str | None

    model_config = {"from_attributes": True}


class ChangeOut(BaseModel):
    id: uuid.UUID
    domain_id: uuid.UUID
    detected_at: datetime
    change_type: str
    before: dict
    after: dict

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
