"""Google-dorking endpoints.

GET  /dorks/catalog                   — categories available per target_type.
POST /dorks/run                       — execute dorks against a target.
GET  /dorks/runs?target=&limit=       — recent runs.
GET  /dorks/runs/{run_id}             — full run + findings.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_db import get_session

from app.db import get_session_factory
from app.dorking import CATEGORIES, run_dorks
from app.models import DorkFinding, DorkRun

router = APIRouter(prefix="/dorks", tags=["dorks"])


async def _session_dep():
    async for s in get_session(get_session_factory()):
        yield s


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


# ── Schemas ────────────────────────────────────────────────────────────────

class CatalogCategory(BaseModel):
    key: str
    label: str
    description: str
    dorks: list[str]   # exposes the templates so the UI can show a preview


class CatalogResponse(BaseModel):
    target_types: dict[str, dict[str, CatalogCategory]]


class RunIn(BaseModel):
    target: str = Field(..., min_length=1, max_length=512)
    target_type: Literal["domain", "email", "ip", "company"]
    categories: list[str] | None = None    # None == all categories for the type
    limit_per_dork: int = Field(5, ge=1, le=10)


class FindingOut(BaseModel):
    id: uuid.UUID
    category: str
    dork: str
    title: str
    url: str
    snippet: str
    source: str
    discovered_at: datetime
    model_config = {"from_attributes": True}


class RunOut(BaseModel):
    id: uuid.UUID
    target: str
    target_type: str
    categories: list[str]
    backend: str
    status: str
    total_findings: int
    error_detail: str | None
    started_at: datetime
    finished_at: datetime | None
    findings: list[FindingOut] = []
    model_config = {"from_attributes": True}


class RunSummary(BaseModel):
    id: uuid.UUID
    target: str
    target_type: str
    backend: str
    status: str
    total_findings: int
    started_at: datetime
    finished_at: datetime | None
    model_config = {"from_attributes": True}


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get(
    "/catalog",
    response_model=CatalogResponse,
    dependencies=[Depends(require_permission("indicator:read"))],
)
async def get_catalog() -> CatalogResponse:
    """Return the curated dork catalog grouped by target_type then category.

    Lets the UI render checkbox groups dynamically instead of hardcoding
    the list — adding a new category in catalog.py shows up here on the
    next deploy.
    """
    out: dict[str, dict[str, CatalogCategory]] = {}
    for ttype, cats in CATEGORIES.items():
        out[ttype] = {
            key: CatalogCategory(
                key=key,
                label=spec["label"],
                description=spec["description"],
                dorks=list(spec["dorks"]),
            )
            for key, spec in cats.items()
        }
    return CatalogResponse(target_types=out)


@router.post(
    "/run",
    response_model=RunOut,
    dependencies=[Depends(require_permission("indicator:write"))],
)
async def run(body: RunIn, request: Request, session: SessionDep) -> RunOut:
    """Execute the requested dork categories against the target.

    Synchronous because the catalog is small (5-35 queries typical) and
    Google CSE responds in <300ms per query — total wall time is usually
    <30s. Falls back to DDG per-query on Google quota / errors.
    """
    google_api_key = getattr(request.app.state, "google_api_key", None)
    google_cse_id  = getattr(request.app.state, "google_cse_id", None)

    run_row = await run_dorks(
        session=session,
        target=body.target.strip(),
        target_type=body.target_type,
        categories=body.categories,
        limit_per_dork=body.limit_per_dork,
        google_api_key=google_api_key,
        google_cse_id=google_cse_id,
    )

    # Re-load with children so the response includes findings.
    findings = (await session.execute(
        select(DorkFinding).where(DorkFinding.run_id == run_row.id)
                           .order_by(DorkFinding.category, DorkFinding.discovered_at)
    )).scalars().all()

    out = RunOut.model_validate(run_row)
    out.findings = [FindingOut.model_validate(f) for f in findings]
    return out


@router.get(
    "/runs",
    response_model=list[RunSummary],
    dependencies=[Depends(require_permission("indicator:read"))],
)
async def list_runs(
    session: SessionDep,
    target: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> list[RunSummary]:
    stmt = select(DorkRun).order_by(DorkRun.started_at.desc()).limit(limit)
    if target:
        stmt = stmt.where(DorkRun.target == target.strip())
    rows = (await session.execute(stmt)).scalars().all()
    return [RunSummary.model_validate(r) for r in rows]


@router.get(
    "/runs/{run_id}",
    response_model=RunOut,
    dependencies=[Depends(require_permission("indicator:read"))],
)
async def get_run(run_id: uuid.UUID, session: SessionDep) -> RunOut:
    run_row = await session.get(DorkRun, run_id)
    if not run_row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "dork run not found")
    findings = (await session.execute(
        select(DorkFinding).where(DorkFinding.run_id == run_id)
                           .order_by(DorkFinding.category, DorkFinding.discovered_at)
    )).scalars().all()
    out = RunOut.model_validate(run_row)
    out.findings = [FindingOut.model_validate(f) for f in findings]
    return out
