from fastapi import APIRouter, BackgroundTasks, Body, Depends, Request

from tip_auth import require_permission
from tip_common import extract_run_id, run_with_callback

from app.ingest import run_full_refresh_cycle, run_refresh_cycle

router = APIRouter(tags=["ingest"])


@router.post("/refresh", status_code=202, dependencies=[Depends(require_permission("actors:write"))])
async def trigger_refresh(
    request: Request,
    background_tasks: BackgroundTasks,
    body: dict | None = Body(None),
):
    """Scheduler trigger: incremental refresh (MITRE + groups + recent victims + correlate)."""
    from app.settings import get_settings

    session_factory = request.app.state.session_factory
    health = request.app.state.source_health
    run_id = extract_run_id(body)
    settings = get_settings()
    jwt = getattr(request.app.state, "service_jwt", "")

    background_tasks.add_task(
        run_with_callback,
        lambda: run_refresh_cycle(session_factory, health),
        scheduler_url=settings.scheduler_url,
        run_id=run_id,
        service_jwt=jwt,
    )
    return {"status": "running", "run_id": run_id, "message": "Refresh started in background"}


@router.post("/refresh/full", status_code=202, dependencies=[Depends(require_permission("actors:write"))])
async def trigger_full_refresh(
    request: Request,
    background_tasks: BackgroundTasks,
    body: dict | None = Body(None),
):
    """First-boot / reconciliation trigger: full historical pull (~80k victims)."""
    from app.settings import get_settings

    session_factory = request.app.state.session_factory
    health = request.app.state.source_health
    run_id = extract_run_id(body)
    settings = get_settings()
    jwt = getattr(request.app.state, "service_jwt", "")

    background_tasks.add_task(
        run_with_callback,
        lambda: run_full_refresh_cycle(session_factory, health),
        scheduler_url=settings.scheduler_url,
        run_id=run_id,
        service_jwt=jwt,
    )
    return {"status": "running", "run_id": run_id, "message": "Full refresh started in background"}
