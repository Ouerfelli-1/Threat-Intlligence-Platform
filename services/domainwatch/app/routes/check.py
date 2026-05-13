from fastapi import APIRouter, BackgroundTasks, Depends, Request

from tip_auth import require_permission

from app.monitor.jobs import run_check_cycle

router = APIRouter(tags=["check"])


@router.post("/check/run", status_code=202, dependencies=[Depends(require_permission("domainwatch:write"))])
async def trigger_check(request: Request, background_tasks: BackgroundTasks):
    session_factory = request.app.state.session_factory
    screenshot_dir = request.app.state.settings.screenshot_dir
    background_tasks.add_task(run_check_cycle, session_factory, screenshot_dir)
    return {"status": "running"}
