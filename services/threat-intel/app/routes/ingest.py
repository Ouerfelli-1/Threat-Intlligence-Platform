from fastapi import APIRouter, BackgroundTasks, Depends, Request

from tip_auth import require_permission

from app.ingest import run_ingestion_cycle

router = APIRouter(tags=["ingest"])


@router.post("/ingest/run", status_code=200, dependencies=[Depends(require_permission("threats:write"))])
async def trigger_ingest(request: Request, background_tasks: BackgroundTasks):
    session_factory = request.app.state.session_factory
    health = request.app.state.source_health
    hibp_key = getattr(request.app.state, "hibp_api_key", "")
    cmdb_url = request.app.state.settings.cmdb_url
    svc_headers = {}
    background_tasks.add_task(
        run_ingestion_cycle, session_factory, health, hibp_key, cmdb_url, svc_headers
    )
    return {"status": "running"}
