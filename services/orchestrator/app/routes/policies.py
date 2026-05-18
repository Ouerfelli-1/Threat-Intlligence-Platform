"""CRUD for AI policies + /policies/decide endpoint."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_db import get_session

from app.db import get_session_factory
from app.models import AIPolicy
from app.policies import resolve_policy, PolicyDecision
from app.schemas import (
    PolicyCreate,
    PolicyDecisionOut,
    PolicyOut,
    PolicyUpdate,
)

router = APIRouter(prefix="/policies", tags=["policies"])

GLOBAL_POLICY_ID = "00000000-0000-0000-0000-000000000001"


async def _session_dep():
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


@router.get(
    "",
    response_model=list[PolicyOut],
    dependencies=[Depends(require_permission("reports:read"))],
)
async def list_policies(
    session: SessionDep,
    scope: str | None = None,
    resource_type: str | None = None,
    active_only: bool = True,
):
    stmt = select(AIPolicy).order_by(AIPolicy.priority.desc())
    if scope:
        stmt = stmt.where(AIPolicy.scope == scope)
    if resource_type:
        stmt = stmt.where(AIPolicy.resource_type == resource_type)
    if active_only:
        stmt = stmt.where(AIPolicy.active.is_(True))
    rows = (await session.execute(stmt)).scalars().all()
    return rows


@router.post(
    "",
    response_model=PolicyOut,
    status_code=201,
    dependencies=[Depends(require_permission("reports:write"))],
)
async def create_policy(body: PolicyCreate, session: SessionDep):
    if body.scope not in ("global", "category", "resource"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "scope must be global|category|resource")
    if body.mode not in ("full_auto", "category_auto", "on_demand"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "mode must be full_auto|category_auto|on_demand")

    now = datetime.now(timezone.utc)
    policy = AIPolicy(
        id=uuid.uuid4(),
        scope=body.scope,
        category=body.category,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        mode=body.mode,
        actions=body.actions,
        cmdb_filter=body.cmdb_filter,
        priority=body.priority,
        active=body.active,
        created_at=now,
        updated_at=now,
    )
    session.add(policy)
    await session.flush()
    return policy


@router.patch(
    "/{policy_id}",
    response_model=PolicyOut,
    dependencies=[Depends(require_permission("reports:write"))],
)
async def update_policy(
    policy_id: uuid.UUID,
    body: PolicyUpdate,
    session: SessionDep,
):
    policy = await session.get(AIPolicy, policy_id)
    if not policy:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found")
    if body.mode is not None:
        if body.mode not in ("full_auto", "category_auto", "on_demand"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "mode must be full_auto|category_auto|on_demand")
        policy.mode = body.mode
    if body.actions is not None:
        policy.actions = body.actions
    if body.cmdb_filter is not None:
        policy.cmdb_filter = body.cmdb_filter
    if body.priority is not None:
        policy.priority = body.priority
    if body.active is not None:
        policy.active = body.active
    policy.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return policy


@router.delete(
    "/{policy_id}",
    status_code=204,
    dependencies=[Depends(require_permission("reports:write"))],
)
async def delete_policy(policy_id: uuid.UUID, session: SessionDep):
    if str(policy_id) == GLOBAL_POLICY_ID:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Cannot delete the seeded global default policy. Deactivate it instead.",
        )
    policy = await session.get(AIPolicy, policy_id)
    if not policy:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found")
    await session.delete(policy)
    await session.flush()


@router.get(
    "/decide",
    response_model=PolicyDecisionOut,
    dependencies=[Depends(require_permission("reports:read"))],
)
async def decide(
    resource_type: str = Query(...),
    resource_id: str = Query(...),
    session: SessionDep = None,  # type: ignore[assignment]
):
    """Return the resolved policy decision for a specific resource."""
    policies = (await session.execute(
        select(AIPolicy).where(AIPolicy.active.is_(True))
    )).scalars().all()

    item = {"id": resource_id}
    decision: PolicyDecision = resolve_policy(item, resource_type, list(policies))
    return PolicyDecisionOut(
        mode=decision.mode,
        actions=decision.actions,
        cmdb_filter=decision.cmdb_filter,
        policy_id=decision.policy_id,
        scope=decision.scope,
    )
