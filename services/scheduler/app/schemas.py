import uuid
from datetime import datetime

from pydantic import BaseModel


class JobInfo(BaseModel):
    id: str
    next_run_time: datetime | None
    trigger: str


class RunOut(BaseModel):
    run_id: uuid.UUID
    job_id: str
    triggered_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    status: str
    http_status: int | None
    error_detail: str | None

    model_config = {"from_attributes": True}


class CompleteRunBody(BaseModel):
    status: str = "success"
    error: str | None = None
