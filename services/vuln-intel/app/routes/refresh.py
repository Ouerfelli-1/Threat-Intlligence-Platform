import time
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy import select

from tip_auth import require_permission

from app.db import get_session_factory
from app.models import CVE, KEV
from app.schemas import RefreshResult
from app.settings import get_settings
from app.sources.epss import sync_epss
from app.sources.kev import sync_kev
from app.sources.nvd import backfill_cves_by_id, sync_recent_cves

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
async def refresh_kev(
    request: Request,
    background: BackgroundTasks,
) -> RefreshResult:
    """Refresh the KEV table from CISA's feed, then kick off a background
    backfill for any newly-discovered KEV CVE IDs we don't have in our
    CVE table yet. Without the backfill, the `kev=true` filter loses
    every KEV entry whose CVE the NVD incremental pull never fetched
    (a slow-drift bug we hit when KEV referenced 1580 historical CVEs
    that pre-dated our first NVD pull).
    """
    settings = get_settings()
    health = request.app.state.source_health
    api_key = getattr(request.app.state, "nvd_api_key", None)
    started = time.monotonic()
    run_id = uuid.uuid4().hex
    async with get_session_factory()() as session:
        seen, added, _ = await sync_kev(session=session, url=settings.kev_url, health=health)

        # Auto-backfill any KEV cve_ids we don't already have. Runs after
        # the response (BackgroundTasks holds a strong ref so we don't
        # repeat the asyncio-GC bug). Idempotent — does nothing if every
        # KEV cve_id is already in vuln.cves.
        missing_stmt = select(KEV.cve_id).where(
            ~select(CVE.cve_id).where(CVE.cve_id == KEV.cve_id).exists()
        )
        missing = [row[0] for row in (await session.execute(missing_stmt)).all()]

    if missing:
        async def _bg():
            async with get_session_factory()() as s:
                await backfill_cves_by_id(
                    session=s, base_url=settings.nvd_base_url,
                    api_key=api_key, health=health, cve_ids=missing,
                )
        background.add_task(_bg)

    duration = int((time.monotonic() - started) * 1000)
    return RefreshResult(
        run_id=run_id, status="success", source="cisa-kev",
        items_seen=seen, items_added=added, items_updated=0,
        duration_ms=duration,
    )


@router.post(
    "/kev-backfill",
    response_model=RefreshResult,
    dependencies=[Depends(require_permission("intelligence:write"))],
)
async def refresh_kev_backfill(
    request: Request,
    background: BackgroundTasks,
    limit: int = 0,
    sync: bool = False,
) -> RefreshResult:
    """Backfill the CVE table for KEV entries we have no CVE row for.

    The "exploited only" filter does CVE INNER JOIN KEV. The incremental
    NVD pull only fetches recent `lastModified` windows, so any KEV entry
    older than the first NVD pull (Heartbleed, Log4Shell, etc.) has no
    matching CVE row and gets dropped by the join — the user sees ~12 hits
    instead of ~1500.

    Fetches each missing CVE individually from NVD's `?cveId=...` API and
    upserts it. Wall time:
      - with NVD_API_KEY:  ~16 min for ~1580 missing entries
      - without:           ~2.5 h (5 req / 30s rate limit)

    Args:
      limit: cap the batch (0 = all missing). Use for testing.
      sync:  block on completion. Default false — returns 202 immediately
             and continues in background. Pass true for small batches.
    """
    settings = get_settings()
    health = request.app.state.source_health
    api_key = getattr(request.app.state, "nvd_api_key", None)
    run_id = uuid.uuid4().hex
    started = time.monotonic()

    # Compute the missing-CVE list once, eagerly, so the caller knows the
    # batch size even when running in background mode.
    async with get_session_factory()() as session:
        stmt = select(KEV.cve_id).where(
            ~select(CVE.cve_id).where(CVE.cve_id == KEV.cve_id).exists()
        )
        missing = [row[0] for row in (await session.execute(stmt)).all()]
    if limit and limit > 0:
        missing = missing[:limit]

    async def _do_backfill():
        async with get_session_factory()() as session:
            await backfill_cves_by_id(
                session=session,
                base_url=settings.nvd_base_url,
                api_key=api_key,
                health=health,
                cve_ids=missing,
            )

    if not sync:
        # Fire-and-forget after the response. BackgroundTasks holds a
        # strong reference so the coroutine isn't GC'd mid-run (the
        # gotcha that bit us when we tried bare asyncio.create_task).
        # Progress visible via source_health.nvd-backfill + CVE count.
        background.add_task(_do_backfill)
        return RefreshResult(
            run_id=run_id, status="running", source="nvd-backfill",
            items_seen=len(missing), items_added=0, items_updated=0,
            duration_ms=0,
        )

    # sync=true path — block on completion. Caller's HTTP client may time
    # out on long runs; primarily useful for small `limit` values.
    try:
        async with get_session_factory()() as session:
            seen, added, updated = await backfill_cves_by_id(
                session=session,
                base_url=settings.nvd_base_url,
                api_key=api_key,
                health=health,
                cve_ids=missing,
            )
    except Exception as e:
        return RefreshResult(
            run_id=run_id, status="failed", source="nvd-backfill",
            items_seen=0, items_added=0, items_updated=0,
            failed=True, error=str(e),
        )
    duration = int((time.monotonic() - started) * 1000)
    return RefreshResult(
        run_id=run_id, status="success", source="nvd-backfill",
        items_seen=seen, items_added=added, items_updated=updated,
        duration_ms=duration,
    )
