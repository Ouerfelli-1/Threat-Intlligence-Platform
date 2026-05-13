from functools import partial

from fastapi import APIRouter, Depends, Request

from tip_auth import require_permission

from app.db import get_session_factory
from app.ingest import run_ingestion_cycle
from app.schemas import IngestResult
from app.settings import get_settings
from app.sources.malbazaar import fetch_recent_samples
from app.sources.threatfox import fetch_recent_iocs

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post(
    "/run",
    response_model=IngestResult,
    dependencies=[Depends(require_permission("iocs:write"))],
)
async def run_ingest(request: Request) -> IngestResult:
    settings = get_settings()
    health = request.app.state.source_health
    abuse_key = getattr(request.app.state, "abusech_api_key", None)

    threatfox_fn = None
    malbazaar_fn = None
    if abuse_key:
        threatfox_fn = partial(
            fetch_recent_iocs,
            api_key=abuse_key,
            days=3,
            base_url=settings.threatfox_url,
            health=health,
        )
        malbazaar_fn = partial(
            fetch_recent_samples,
            api_key=abuse_key,
            base_url=settings.malbazaar_url,
            health=health,
        )

    result = await run_ingestion_cycle(
        session_factory=get_session_factory(),
        health=health,
        threatfox_fn=threatfox_fn,
        malbazaar_fn=malbazaar_fn,
        otx_fn=None,
    )
    return IngestResult(**result)
