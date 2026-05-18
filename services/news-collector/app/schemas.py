import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FeedBase(BaseModel):
    name: str
    url: str
    kind: str = "rss"
    active: bool = True
    reliability: float = Field(0.7, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)


class FeedCreate(FeedBase):
    pass


class FeedUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    active: bool | None = None
    reliability: float | None = Field(None, ge=0.0, le=1.0)
    tags: list[str] | None = None


class FeedOut(FeedBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    added_at: datetime
    last_pulled_at: datetime | None


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    url: str
    source_name: str
    author: str | None
    published_at: datetime | None
    fetched_at: datetime
    summary: str | None
    tags: list[str]
    confidence_score: float | None
    analyst_status: str = "unreviewed"


class ArticleList(BaseModel):
    items: list[ArticleOut]
    total: int


class IngestResult(BaseModel):
    run_id: str
    status: str
    feeds_attempted: int
    feeds_succeeded: int
    articles_added: int
    articles_seen: int
    failed_sources: list[str]


class AnalystStatusUpdate(BaseModel):
    analyst_status: str = Field(..., pattern=r"^(unreviewed|relevant|not_relevant|escalated|reviewed)$")


class InsightOverrideIn(BaseModel):
    analyst_override: dict


class AnalyzeRequest(BaseModel):
    actions: list[str] | None = None
    flowviz: bool = True
    model: str | None = None


class InsightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    article_id: uuid.UUID | None = None
    payload: dict
    model_name: str | None = None
    prompt_version: str | None = None
    generated_at: datetime | None = None
    analyst_override: dict | None = None
