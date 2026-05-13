from fastapi import APIRouter, BackgroundTasks, Depends, Request

from tip_auth import require_permission

from app.ingest import run_full_refresh_cycle, run_refresh_cycle

router = APIRouter(tags=["ingest"])


@router.post("/refresh", status_code=202, dependencies=[Depends(require_permission("actors:write"))])
async def trigger_refresh(request: Request, background_tasks: BackgroundTasks):
    """Scheduler trigger: incremental refresh (MITRE + groups + recent victims)."""
    session_factory = request.app.state.session_factory
    health = request.app.state.source_health
    background_tasks.add_task(run_refresh_cycle, session_factory, health)
    return {"status": "running", "message": "Refresh started in background"}


@router.post("/refresh/full", status_code=202, dependencies=[Depends(require_permission("actors:write"))])
async def trigger_full_refresh(request: Request, background_tasks: BackgroundTasks):
    """First-boot / reconciliation trigger: full historical pull (~80k victims)."""
    session_factory = request.app.state.session_factory
    health = request.app.state.source_health
    background_tasks.add_task(run_full_refresh_cycle, session_factory, health)
    return {"status": "running", "message": "Full refresh started in background"}
