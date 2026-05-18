import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_common import NotFoundError, resolve_sort
from tip_db import get_session

from app.db import get_session_factory
from app.models import HIBPBreach, Threat, ThreatInsight
from app.schemas import (
    AnalystStatusUpdate,
    AnalyzeRequest,
    HIBPBreachOut,
    InsightOverrideIn,
    ThreatCreateManual,
    ThreatInsightOut,
    ThreatList,
    ThreatOut,
)

log = logging.getLogger(__name__)

router = APIRouter(tags=["threats"])


async def _session_dep():
    # async-generator wrapper: FastAPI iterates exactly once,
    # yielding the live session into the endpoint.
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


_THREAT_SORT_COLS = {
    "observed_at":      Threat.observed_at,
    "title":            Threat.title,
    "severity":         Threat.severity,
    "type":             Threat.type,
    "confidence_score": Threat.confidence_score,
    "analyst_status":   Threat.analyst_status,
}


@router.get(
    "/threats",
    response_model=ThreatList,
    dependencies=[Depends(require_permission("threats:read"))],
)
async def list_threats(
    session: SessionDep,
    type: str | None = Query(None),
    since: datetime | None = Query(None),
    severity: str | None = Query(None),
    q: str | None = Query(None),
    include_not_relevant: bool = Query(False),
    sort_by: str | None = Query(None, description=f"One of: {', '.join(sorted(_THREAT_SORT_COLS))}"),
    sort_dir: str | None = Query(None, description="asc | desc"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(Threat)
    if not include_not_relevant:
        stmt = stmt.where(Threat.analyst_status != "not_relevant")
    if type:
        stmt = stmt.where(Threat.type == type)
    if since:
        stmt = stmt.where(Threat.observed_at >= since)
    if severity:
        stmt = stmt.where(Threat.severity == severity)
    if q:
        stmt = stmt.where(Threat.title.ilike(f"%{q}%"))
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(
        resolve_sort(sort_by, sort_dir, _THREAT_SORT_COLS, default="observed_at")
    ).offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return ThreatList(items=[ThreatOut.model_validate(r) for r in rows], total=total)


@router.get("/threats/{threat_id}", response_model=ThreatOut, dependencies=[Depends(require_permission("threats:read"))])
async def get_threat(threat_id: UUID, session: SessionDep):
    result = await session.execute(select(Threat).where(Threat.id == threat_id))
    threat = result.scalar_one_or_none()
    if not threat:
        raise NotFoundError(f"Threat {threat_id} not found")
    return threat


@router.post("/threats", response_model=ThreatOut, status_code=201, dependencies=[Depends(require_permission("threats:write"))])
async def create_threat_manual(body: ThreatCreateManual, session: SessionDep):
    """Analyst-created threat entry."""
    from tip_auth import current_user
    threat = Threat(
        id=_uuid.uuid4(),
        type=body.type,
        title=body.title,
        source="analyst:manual",
        observed_at=datetime.now(timezone.utc),
        summary=body.summary,
        severity=body.severity,
        details=body.details,
        confidence_score=0.95,
        confidence_inputs={"source_reliability": 0.95, "weights_version": "manual_v1"},
        analyst_status="reviewed",
        manual_source="analyst:manual",
    )
    session.add(threat)
    await session.flush()
    return ThreatOut.model_validate(threat)


@router.patch("/threats/{threat_id}/status", response_model=ThreatOut, dependencies=[Depends(require_permission("threats:write"))])
async def update_threat_status(
    threat_id: UUID,
    body: AnalystStatusUpdate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: SessionDep,
):
    result = await session.execute(select(Threat).where(Threat.id == threat_id))
    threat = result.scalar_one_or_none()
    if not threat:
        raise NotFoundError(f"Threat {threat_id} not found")
    old_status = threat.analyst_status
    threat.analyst_status = body.analyst_status
    await session.flush()

    # When marked 'relevant', auto-add affected products to CMDB
    if body.analyst_status == "relevant" and old_status != "relevant":
        products = _extract_products_from_threat(threat)
        if products:
            from app.settings import get_settings
            settings = get_settings()
            jwt = getattr(request.app.state, "service_jwt", "") or ""
            for product in products:
                background_tasks.add_task(
                    _auto_add_product, settings.cmdb_url, jwt, "threat", str(threat_id), product
                )

    return ThreatOut.model_validate(threat)


def _extract_products_from_threat(threat: Threat) -> list[str]:
    """Extract affected product names from threat details."""
    products: list[str] = []
    details = threat.details or {}
    if isinstance(details, dict):
        for prod in details.get("affected_products", []):
            if isinstance(prod, str) and prod not in products:
                products.append(prod)
    return products[:5]


async def _auto_add_product(
    cmdb_url: str, jwt: str, resource_type: str, resource_id: str, product_name: str
) -> None:
    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=10) as c:
            r = await c.post(
                f"{cmdb_url}/profile/auto-add",
                json={
                    "source_resource_type": resource_type,
                    "source_resource_id": resource_id,
                    "product_name": product_name,
                },
            )
            if r.status_code < 300:
                log.info("Auto-added product '%s' from %s %s", product_name, resource_type, resource_id)
            else:
                log.warning("CMDB auto-add returned %d: %s", r.status_code, r.text[:200])
    except Exception:
        log.exception("Failed to auto-add product '%s' to CMDB", product_name)


@router.get("/threats/{threat_id}/insight", response_model=ThreatInsightOut, dependencies=[Depends(require_permission("threats:read"))])
async def get_threat_insight(threat_id: UUID, session: SessionDep):
    result = await session.execute(
        select(ThreatInsight).where(ThreatInsight.threat_id == threat_id)
    )
    insight = result.scalar_one_or_none()
    if not insight:
        raise NotFoundError(f"No insight for threat {threat_id}")
    return insight


@router.put("/threats/{threat_id}/insight/override", response_model=ThreatInsightOut, dependencies=[Depends(require_permission("threats:write"))])
async def override_threat_insight(threat_id: UUID, body: InsightOverrideIn, session: SessionDep):
    result = await session.execute(
        select(ThreatInsight).where(ThreatInsight.threat_id == threat_id)
    )
    insight = result.scalar_one_or_none()
    if not insight:
        raise NotFoundError(f"No insight for threat {threat_id}")
    insight.analyst_override = body.analyst_override
    await session.flush()
    return ThreatInsightOut.model_validate(insight)


@router.post(
    "/threats/{threat_id}/analyze",
    status_code=202,
    dependencies=[Depends(require_permission("threats:write"))],
)
async def analyze_threat(
    threat_id: UUID,
    request: Request,
    body: AnalyzeRequest | None = None,
    session: SessionDep = None,  # type: ignore[assignment]
):
    from app.settings import get_settings

    result = await session.execute(select(Threat).where(Threat.id == threat_id))
    threat = result.scalar_one_or_none()
    if not threat:
        raise NotFoundError(f"Threat {threat_id} not found")
    if body is None:
        body = AnalyzeRequest()

    settings = get_settings()
    jwt = getattr(request.app.state, "service_jwt", "")
    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}

    actions = body.actions or ["extract_iocs", "map_ttps"]
    if body.flowviz:
        actions = list(set(actions) | {"flowviz"})

    async with httpx.AsyncClient(headers=headers, timeout=30) as c:
        r = await c.post(
            f"{settings.orchestrator_url}/actions/run",
            json={
                "resource_type": "threat",
                "resource_id": str(threat_id),
                "actions": actions,
            },
        )
        return r.json()


@router.get("/hibp-breaches", response_model=list[HIBPBreachOut], dependencies=[Depends(require_permission("threats:read"))])
async def list_breaches(
    session: SessionDep,
    is_verified: bool | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(HIBPBreach)
    if is_verified is not None:
        stmt = stmt.where(HIBPBreach.is_verified == is_verified)
    stmt = stmt.order_by(HIBPBreach.added_date.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()
