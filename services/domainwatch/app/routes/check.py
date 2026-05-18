from fastapi import APIRouter, BackgroundTasks, Body, Depends, Request

from tip_auth import require_permission
from tip_common import extract_run_id, run_with_callback

from app.monitor.jobs import run_check_cycle

router = APIRouter(tags=["check"])


@router.post("/check/run", status_code=202, dependencies=[Depends(require_permission("domainwatch:write"))])
async def trigger_check(
    request: Request,
    background_tasks: BackgroundTasks,
    body: dict | None = Body(None),
):
    session_factory = request.app.state.session_factory
    screenshot_dir = request.app.state.settings.screenshot_dir
    run_id = extract_run_id(body)
    scheduler_url = request.app.state.settings.scheduler_url
    jwt = getattr(request.app.state, "service_jwt", "")

    background_tasks.add_task(
        run_with_callback,
        lambda: run_check_cycle(session_factory, screenshot_dir),
        scheduler_url=scheduler_url,
        run_id=run_id,
        service_jwt=jwt,
    )
    return {"status": "running", "run_id": run_id}
