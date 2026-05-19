"""
APScheduler job definitions and registration.
Uses a sync SQLAlchemyJobStore (psycopg2) and AsyncIOExecutor.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

import httpx
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobRunHistory

log = logging.getLogger(__name__)

# max_runtime in seconds per job
# NOTE: short intervals for live-test mode. Restore production cadences after validation.
JOB_CONFIGS = [
    {"id": "news_pull",          "url_attr": "news_collector_url",  "path": "/ingest/run",    "method": "POST", "schedule": IntervalTrigger(minutes=10),   "max_runtime": 600},
    {"id": "threat_intel_pull",  "url_attr": "threat_intel_url",    "path": "/ingest/run",    "method": "POST", "schedule": IntervalTrigger(minutes=15),   "max_runtime": 600},
    {"id": "vuln_cve_refresh",   "url_attr": "vuln_intel_url",      "path": "/refresh/nvd",   "method": "POST", "schedule": IntervalTrigger(minutes=20),   "max_runtime": 1800},
    {"id": "vuln_kev_refresh",   "url_attr": "vuln_intel_url",      "path": "/refresh/kev",   "method": "POST", "schedule": IntervalTrigger(minutes=12),   "max_runtime": 300},
    # EPSS daily snapshot is ~333K rows — well under 30 min on FIRST.org's
    # CSV but the old 300s cap was too tight. Bumped to 1800.
    {"id": "vuln_epss_refresh",  "url_attr": "vuln_intel_url",      "path": "/refresh/epss",  "method": "POST", "schedule": IntervalTrigger(minutes=18),   "max_runtime": 1800},
    {"id": "ioc_pull",           "url_attr": "ioc_collector_url",   "path": "/ingest/run",    "method": "POST", "schedule": IntervalTrigger(minutes=8),    "max_runtime": 600},
    {"id": "actors_refresh",     "url_attr": "threat_actors_url",   "path": "/refresh",       "method": "POST", "schedule": IntervalTrigger(minutes=30),   "max_runtime": 1800},
    {"id": "asm_discovery",      "url_attr": "asm_url",             "path": "/scan/run",      "method": "POST", "schedule": IntervalTrigger(minutes=25),   "max_runtime": 3600},
    {"id": "domainwatch_check",  "url_attr": "domainwatch_url",     "path": "/check/run",     "method": "POST", "schedule": IntervalTrigger(minutes=20),   "max_runtime": 3600},
    {"id": "wazuh_sync",         "url_attr": "integrations_url",    "path": "/wazuh/sync",    "method": "POST", "schedule": IntervalTrigger(minutes=10),   "max_runtime": 600},
    {"id": "orchestrator_analysis","url_attr":"orchestrator_url",    "path": "/analyze",       "method": "POST", "schedule": IntervalTrigger(minutes=15),   "max_runtime": 1800},
    {"id": "geo_prediction",     "url_attr": "orchestrator_url",    "path": "/analyze/geo",   "method": "POST", "schedule": IntervalTrigger(minutes=25),   "max_runtime": 1800},
]

_scheduler: AsyncIOScheduler | None = None
_settings = None
_session_factory = None

# Service-JWT cache. main.py calls set_jwt_refresher() once at startup to
# install the initial JWT obtained via wire_auth, plus a refresher closure
# that re-invokes obtain_service_jwt when the cached one expires (which
# manifests as a 401 from any downstream service).
_service_jwt: str = ""
_jwt_refresher = None  # async () -> str


def set_jwt_refresher(initial_jwt: str, refresher) -> None:
    global _service_jwt, _jwt_refresher
    _service_jwt = initial_jwt or ""
    _jwt_refresher = refresher


def _auth_headers() -> dict:
    if _service_jwt:
        return {"Authorization": f"Bearer {_service_jwt}"}
    return {}


def build_scheduler(settings, session_factory) -> AsyncIOScheduler:
    global _scheduler, _settings, _session_factory
    _settings = settings
    _session_factory = session_factory

    jobstore = SQLAlchemyJobStore(url=settings.sync_db_url, tableschema="scheduler")
    scheduler = AsyncIOScheduler(
        jobstores={"default": jobstore},
        executors={"default": AsyncIOExecutor()},
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300},
    )

    for cfg in JOB_CONFIGS:
        scheduler.add_job(
            _fire_job,
            cfg["schedule"],
            id=cfg["id"],
            args=[cfg["id"], cfg["url_attr"], cfg["path"], cfg.get("method", "POST"), cfg.get("max_runtime", 600)],
            replace_existing=True,
        )

    # Watchdog: marks timed-out runs every 60s
    scheduler.add_job(
        _watchdog,
        IntervalTrigger(seconds=60),
        id="_watchdog",
        replace_existing=True,
    )

    _scheduler = scheduler
    return scheduler


async def _fire_job(job_id: str, url_attr: str, path: str, method: str = "POST", max_runtime: int = 600) -> None:
    run_id = uuid.uuid4()
    base_url = getattr(_settings, url_attr, "")
    if not base_url:
        log.warning("scheduler job=%s skipped: no URL configured", job_id)
        return

    triggered_at = datetime.now(timezone.utc)
    async with _session_factory() as session:
        run = JobRunHistory(
            run_id=run_id,
            job_id=job_id,
            triggered_at=triggered_at,
            status="running",
        )
        session.add(run)
        await session.commit()

    # Use max_runtime as the HTTP timeout so slow jobs (NVD, IOC bulk, EPSS
    # download of 333K rows) aren't cut short. Cap at 30 min — long enough for
    # the EPSS snapshot, short enough that a genuinely-hung target gets noticed.
    # connect timeout stays at 10 s.
    http_timeout = httpx.Timeout(connect=10.0, read=min(max_runtime, 1800), write=60.0, pool=10.0)

    global _service_jwt
    start = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(timeout=http_timeout) as client:
            fn = getattr(client, method.lower())
            resp = await fn(
                f"{base_url}{path}",
                json={"run_id": str(run_id)},
                headers=_auth_headers(),
            )

            # 401: cached service JWT likely expired. Refresh once and
            # retry — going from "every job 401s for 24h" (the silent
            # drift we hit) to a one-line self-heal.
            if resp.status_code == 401 and _jwt_refresher is not None:
                log.warning("scheduler job=%s got 401, refreshing service JWT", job_id)
                try:
                    new_jwt = await _jwt_refresher()
                    if new_jwt:
                        _service_jwt = new_jwt
                        resp = await fn(
                            f"{base_url}{path}",
                            json={"run_id": str(run_id)},
                            headers=_auth_headers(),
                        )
                except Exception as ref_exc:
                    log.error("scheduler jwt_refresh_failed: %r", ref_exc)

        http_status = resp.status_code
        # 202 means the service accepted the work and will run it asynchronously.
        # The actual outcome will arrive via POST /internal/runs/{run_id}/complete.
        # Until then the row stays as "running" so the UI doesn't claim success
        # before the background task actually finishes.
        if 200 <= resp.status_code < 300 and resp.status_code != 202:
            status = "success"
            error_detail = None
        elif resp.status_code == 202:
            status = "running"
            error_detail = None
        else:
            status = "failed"
            error_detail = resp.text[:500]
        log.info("scheduler job=%s run_id=%s status=%s http=%d", job_id, run_id, status, http_status)
    except Exception as exc:
        http_status = None
        status = "failed"
        # Use repr() so exceptions with no message (e.g. ReadTimeout) still show their type
        error_detail = repr(exc)[:500]
        log.error("scheduler job=%s run_id=%s error=%r", job_id, run_id, exc)

    elapsed_ms = int((asyncio.get_event_loop().time() - start) * 1000)
    async with _session_factory() as session:
        run = await session.get(JobRunHistory, run_id)
        if run:
            # Only stamp completed_at for terminal states; "running" jobs will be
            # closed by the callback or the watchdog.
            if status != "running":
                run.completed_at = datetime.now(timezone.utc)
                run.duration_ms = elapsed_ms
            run.status = status
            run.http_status = http_status
            run.error_detail = error_detail
            await session.commit()


async def _watchdog() -> None:
    from datetime import timedelta
    from sqlalchemy import select, update

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    async with _session_factory() as session:
        await session.execute(
            JobRunHistory.__table__.update()
            .where(JobRunHistory.status == "running")
            .where(JobRunHistory.triggered_at < cutoff)
            .values(status="timeout", completed_at=datetime.now(timezone.utc))
        )
        await session.commit()


async def complete_run(run_id: uuid.UUID, status: str, error: str | None = None) -> None:
    """Called by services via /internal/runs/{run_id}/complete."""
    async with _session_factory() as session:
        run = await session.get(JobRunHistory, run_id)
        if run:
            run.completed_at = datetime.now(timezone.utc)
            run.status = status
            run.error_detail = error
            if run.triggered_at:
                elapsed = (run.completed_at - run.triggered_at).total_seconds()
                run.duration_ms = int(elapsed * 1000)
            await session.commit()
