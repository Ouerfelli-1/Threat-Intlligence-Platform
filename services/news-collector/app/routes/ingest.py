import uuid

from fastapi import APIRouter, Depends, Request

from tip_auth import require_permission

from app.db import get_session_factory
from app.ingest import run_ingestion_cycle
from app.schemas import IngestResult
from app.settings import get_settings

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post(
    "/run",
    response_model=IngestResult,
    dependencies=[Depends(require_permission("intelligence:write"))],
)
async def run_ingest(request: Request) -> IngestResult:
    settings = get_settings()
    health = request.app.state.source_health
    run_id = (await request.json() or {}).get("run_id") if request.headers.get("content-type", "").startswith("application/json") else None
    run_id = run_id or uuid.uuid4().hex
    result = await run_ingestion_cycle(
        session_factory=get_session_factory(),
        user_agent=settings.user_agent,
        health=health,
        run_id=run_id,
    )
    return IngestResult(**result)
