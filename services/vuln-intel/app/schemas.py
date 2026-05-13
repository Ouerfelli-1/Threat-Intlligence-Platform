from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class CVEOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cve_id: str
    published_at: datetime | None
    last_modified_at: datetime | None
    description: str | None
    cvss_v3_score: float | None
    cvss_v3_vector: str | None
    severity: str | None
    cwe: list[str]
    affected_products: dict
    references: list[str]


class CVEDetail(CVEOut):
    epss: float | None = None
    epss_percentile: float | None = None
    kev: bool = False
    kev_date_added: date | None = None
    kev_ransomware_use: bool = False


class CVEList(BaseModel):
    items: list[CVEOut]
    total: int


class KEVOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cve_id: str
    vendor: str | None
    product: str | None
    name: str | None
    date_added: date | None
    due_date: date | None
    ransomware_use: bool
    notes: str | None


class RefreshResult(BaseModel):
    run_id: str
    status: str
    source: str
    items_seen: int
    items_added: int
    items_updated: int
    duration_ms: int = 0
    failed: bool = False
    error: str | None = None
