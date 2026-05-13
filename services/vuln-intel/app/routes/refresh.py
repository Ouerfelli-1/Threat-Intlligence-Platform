import time
import uuid

from fastapi import APIRouter, Depends, Request

from tip_auth import require_permission

from app.db import get_session_factory
from app.schemas import RefreshResult
from app.settings import get_settings
from app.sources.epss import sync_epss
from app.sources.kev import sync_kev
from app.sources.nvd import sync_recent_cves

router = APIRouter(prefix="/refresh", tags=["refresh"])


@router.post(
    "/nvd",
    response_model=RefreshResult,
    dependencies=[Depends(require_permission("intelligence:write"))],
)
async def refresh_nvd(request: Request) -> RefreshResult:
    settings = get_settings()
    health = request.app.state.source_health
    api_key = getattr(request.app.state, "nvd_api_key", None)
    started = time.monotonic()
    run_id = uuid.uuid4().hex
    async with get_session_factory()() as session:
        try:
            seen, added, updated = await sync_recent_cves(
                session=session,
                base_url=settings.nvd_base_url,
                api_key=api_key,
                health=health,
            )
            duration = int((time.monotonic() - started) * 1000)
            return RefreshResult(
                run_id=run_id, status="success", source="nvd",
                items_seen=seen, items_added=added, items_updated=updated,
                duration_ms=duration,
            )
        except Exception as e:
            return RefreshResult(
                run_id=run_id, status="failed", source="nvd",
                items_seen=0, items_added=0, items_updated=0,
                failed=True, error=str(e),
            )


@router.post(
    "/epss",
    response_model=RefreshResult,
    dependencies=[Depends(require_permission("intelligence:write"))],
)
async def refresh_epss(request: Request) -> RefreshResult:
    settings = get_settings()
    health = request.app.state.source_health
    started = time.monotonic()
    run_id = uuid.uuid4().hex
    async with get_session_factory()() as session:
        seen, added, _ = await sync_epss(session=session, url=settings.epss_url, health=health)
    duration = int((time.monotonic() - started) * 1000)
    return RefreshResult(
        run_id=run_id, status="success", source="epss",
        items_seen=seen, items_added=added, items_updated=0,
        duration_ms=duration,
    )


@router.post(
    "/kev",
    response_model=RefreshResult,
    dependencies=[Depends(require_permission("intelligence:write"))],
)
async def refresh_kev(request: Request) -> RefreshResult:
    settings = get_settings()
    health = request.app.state.source_health
    started = time.monotonic()
    run_id = uuid.uuid4().hex
    async with get_session_factory()() as session:
        seen, added, _ = await sync_kev(session=session, url=settings.kev_url, health=health)
    duration = int((time.monotonic() - started) * 1000)
    return RefreshResult(
        run_id=run_id, status="success", source="cisa-kev",
        items_seen=seen, items_added=added, items_updated=0,
        duration_ms=duration,
    )
