import uuid as _uuid
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import current_user, require_permission
from tip_common import NotFoundError
from tip_db import get_session

from app.db import get_session_factory
from app.models import Actor, ActorInsight, ActorTool, ActorTTP, RansomwareGroup, Tool
from app.schemas import (
    ActorCreateManual,
    ActorDetailOut,
    ActorInsightOut,
    ActorList,
    ActorOut,
    AnalyzeRequest,
    AnalystStatusUpdate,
    InsightOverrideIn,
    RansomwareGroupOut,
)

router = APIRouter(prefix="/actors", tags=["actors"])


async def _session_dep():
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


@router.get(
    "",
    response_model=ActorList,
    dependencies=[Depends(require_permission("actors:read"))],
)
async def list_actors(
    session: SessionDep,
    q: str | None = Query(None, description="Free-text search across name + aliases + description"),
    name: str | None = Query(None, description="Substring match on name (legacy alias for q)"),
    sector: str | None = Query(None),
    country: str | None = Query(None),
    motivation: str | None = Query(None),
    status: str | None = Query(None),
    include_not_relevant: bool = Query(False),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    stmt = select(Actor)
    if not include_not_relevant:
        stmt = stmt.where(Actor.analyst_status != "not_relevant")

    search_term = q or name
    if search_term:
        like = f"%{search_term}%"
        # Match identity fields only (name / aliases / mitre id). Description
        # matching was too greedy — searching "lockbit" pulled in every actor
        # whose profile mentioned LockBit as a related group. If a description
        # search is ever wanted, expose it as a separate query parameter.
        stmt = stmt.where(
            or_(
                Actor.name.ilike(like),
                func.array_to_string(Actor.aliases, ",").ilike(like),
                Actor.mitre_id.ilike(like),
            )
        )
    if sector:
        stmt = stmt.where(Actor.target_sectors.any(sector))
    if country:
        stmt = stmt.where(Actor.target_countries.any(country))
    if motivation:
        stmt = stmt.where(Actor.motivation.any(motivation))
    if status:
        stmt = stmt.where(Actor.status == status)

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Actor.name).offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return ActorList(items=[ActorOut.model_validate(r) for r in rows], total=total)


@router.get(
    "/{actor_id}",
    response_model=ActorDetailOut,
    dependencies=[Depends(require_permission("actors:read"))],
)
async def get_actor(actor_id: UUID, session: SessionDep):
    result = await session.execute(select(Actor).where(Actor.id == actor_id))
    actor = result.scalar_one_or_none()
    if not actor:
        raise NotFoundError(f"Actor {actor_id} not found")

    ttps_result = await session.execute(
        select(ActorTTP).where(ActorTTP.actor_id == actor_id).order_by(ActorTTP.technique_id)
    )
    tools_result = await session.execute(
        select(Tool).join(ActorTool, Tool.id == ActorTool.tool_id).where(ActorTool.actor_id == actor_id)
    )
    rg_result = await session.execute(
        select(RansomwareGroup).where(RansomwareGroup.actor_id == actor_id).order_by(RansomwareGroup.name)
    )

    return ActorDetailOut(
        **ActorOut.model_validate(actor).model_dump(),
        ttps=ttps_result.scalars().all(),
        tools=tools_result.scalars().all(),
        ransomware_groups=[RansomwareGroupOut.model_validate(g) for g in rg_result.scalars().all()],
    )


@router.post(
    "",
    response_model=ActorOut,
    status_code=201,
    dependencies=[Depends(require_permission("actors:write"))],
)
async def create_actor_manual(body: ActorCreateManual, session: SessionDep):
    """Analyst-created actor entry (mitre_id optional)."""
    actor = Actor(
        id=_uuid.uuid4(),
        name=body.name,
        mitre_id=body.mitre_id,
        aliases=body.aliases,
        origin_country=body.origin_country,
        description=body.description,
        motivation=body.motivation,
        target_sectors=body.target_sectors,
        target_countries=body.target_countries,
        analyst_status="reviewed",
    )
    session.add(actor)
    await session.flush()
    return ActorOut.model_validate(actor)


@router.patch(
    "/{actor_id}/status",
    response_model=ActorOut,
    dependencies=[Depends(require_permission("actors:write"))],
)
async def update_actor_status(actor_id: UUID, body: AnalystStatusUpdate, session: SessionDep):
    result = await session.execute(select(Actor).where(Actor.id == actor_id))
    actor = result.scalar_one_or_none()
    if not actor:
        raise NotFoundError(f"Actor {actor_id} not found")
    actor.analyst_status = body.analyst_status
    await session.flush()
    return ActorOut.model_validate(actor)


@router.get(
    "/{actor_id}/insight",
    response_model=ActorInsightOut,
    dependencies=[Depends(require_permission("actors:read"))],
)
async def get_actor_insight(actor_id: UUID, session: SessionDep):
    result = await session.execute(
        select(ActorInsight).where(ActorInsight.actor_id == actor_id)
    )
    insight = result.scalar_one_or_none()
    if not insight:
        raise NotFoundError(f"No insight for actor {actor_id}")
    return insight


@router.put(
    "/{actor_id}/insight/override",
    response_model=ActorInsightOut,
    dependencies=[Depends(require_permission("actors:write"))],
)
async def override_actor_insight(actor_id: UUID, body: InsightOverrideIn, session: SessionDep):
    result = await session.execute(
        select(ActorInsight).where(ActorInsight.actor_id == actor_id)
    )
    insight = result.scalar_one_or_none()
    if not insight:
        raise NotFoundError(f"No insight for actor {actor_id}")
    insight.analyst_override = body.analyst_override
    await session.flush()
    return ActorInsightOut.model_validate(insight)


@router.post(
    "/{actor_id}/analyze",
    status_code=202,
    dependencies=[Depends(require_permission("actors:write"))],
)
async def analyze_actor(
    actor_id: UUID,
    request: Request,
    body: AnalyzeRequest | None = None,
    session: SessionDep = None,  # type: ignore[assignment]
):
    from app.settings import get_settings

    result = await session.execute(select(Actor).where(Actor.id == actor_id))
    actor = result.scalar_one_or_none()
    if not actor:
        raise NotFoundError(f"Actor {actor_id} not found")
    if body is None:
        body = AnalyzeRequest()

    settings = get_settings()
    jwt = getattr(request.app.state, "service_jwt", "")
    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}

    actions = body.actions or ["actor_likelihood", "map_ttps"]
    if body.flowviz:
        actions = list(set(actions) | {"flowviz"})

    async with httpx.AsyncClient(headers=headers, timeout=30) as c:
        r = await c.post(
            f"{settings.orchestrator_url}/actions/run",
            json={
                "resource_type": "actor",
                "resource_id": str(actor_id),
                "actions": actions,
            },
        )
        return r.json()


@router.get(
    "/{actor_id}/ttps",
    response_model=list,
    dependencies=[Depends(require_permission("actors:read"))],
)
async def list_actor_ttps(actor_id: UUID, session: SessionDep):
    result = await session.execute(
        select(ActorTTP).where(ActorTTP.actor_id == actor_id).order_by(ActorTTP.technique_id)
    )
    return result.scalars().all()


@router.get(
    "/{actor_id}/ransomware",
    response_model=list[RansomwareGroupOut],
    dependencies=[Depends(require_permission("actors:read"))],
)
async def list_actor_ransomware(actor_id: UUID, session: SessionDep):
    """Ransomware groups correlated with this MITRE actor."""
    result = await session.execute(
        select(RansomwareGroup)
        .where(RansomwareGroup.actor_id == actor_id)
        .order_by(RansomwareGroup.name)
    )
    return [RansomwareGroupOut.model_validate(g) for g in result.scalars().all()]
