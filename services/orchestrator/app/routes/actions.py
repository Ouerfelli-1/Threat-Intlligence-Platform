"""Action dispatch endpoint: POST /actions/run."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_auth import require_permission
from tip_db import get_session

from app.actions import get_actions
from app.context import fetch_company_profile
from app.db import get_session_factory
from app.models import ActionRun
from app.schemas import ActionRunOut, ActionRunRequest

router = APIRouter(tags=["actions"])


async def _session_dep():
    async for session in get_session(get_session_factory()):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session_dep)]


@router.post(
    "/actions/run",
    response_model=list[ActionRunOut],
    status_code=202,
    dependencies=[Depends(require_permission("reports:write"))],
)
async def run_actions(
    body: ActionRunRequest,
    request: Request,
    background: BackgroundTasks,
    session: SessionDep,
):
    """Dispatch one or more actions against a resource.

    Each requested action gets its own ``ActionRun`` row.  If the action
    finishes quickly it is returned inline; otherwise it completes in the
    background.
    """
    registry = get_actions()
    ai = request.app.state.ai_client
    settings = request.app.state.settings
    jwt = getattr(request.app.state, "service_jwt", "")

    runs: list[ActionRun] = []
    for action_name in body.actions:
        if action_name not in registry:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Unknown action: {action_name}",
            )
        now = datetime.now(timezone.utc)
        run_row = ActionRun(
            id=uuid.uuid4(),
            resource_type=body.resource_type,
            resource_id=body.resource_id,
            action=action_name,
            status="pending",
            started_at=now,
        )
        session.add(run_row)
        runs.append(run_row)

    await session.flush()

    # Kick off all actions as background tasks
    for run_row in runs:
        action_fn = registry[run_row.action]

        async def _execute(fn=action_fn, row_id=run_row.id, rtype=body.resource_type, rid=body.resource_id):
            # Build minimal item dict — the action module fetches more if needed
            item = {"id": rid, "resource_type": rtype}
            context = {"company_profile": await fetch_company_profile(settings, jwt)}

            async with get_session_factory()() as bg_session:
                row = await bg_session.get(ActionRun, row_id)
                if not row:
                    return
                row.status = "running"
                await bg_session.flush()
                try:
                    output = await fn(ai, item, context, settings, jwt)
                    row.status = "success"
                    row.output = output
                except Exception as exc:
                    row.status = "error"
                    row.error = str(exc)[:2000]
                row.completed_at = datetime.now(timezone.utc)
                await bg_session.commit()

        background.add_task(_execute)

    return runs


@router.get(
    "/actions/runs",
    response_model=list[ActionRunOut],
    dependencies=[Depends(require_permission("reports:read"))],
)
async def list_action_runs(
    session: SessionDep,
    resource_type: str | None = None,
    resource_id: str | None = None,
    limit: int = 50,
):
    stmt = select(ActionRun).order_by(ActionRun.started_at.desc()).limit(limit)
    if resource_type:
        stmt = stmt.where(ActionRun.resource_type == resource_type)
    if resource_id:
        stmt = stmt.where(ActionRun.resource_id == resource_id)
    rows = (await session.execute(stmt)).scalars().all()
    return rows
