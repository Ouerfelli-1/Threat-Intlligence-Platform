"""Helper for services that handle long-running scheduler-triggered jobs.

Background:
    The scheduler fires `POST {service}/<path>` for each job. Many of our
    refresh endpoints return 202 immediately and run the work in a background
    task. Before this helper, the scheduler logged `status=success` as soon as
    it got the 202 — even if the actual ingest later crashed. That gave a
    false-green view of the platform health.

Fix:
    When an endpoint accepts a scheduler-triggered call, it extracts the
    `run_id` from the request body (the scheduler always sends it), kicks off
    its background task, and the task calls `notify_scheduler_complete` at the
    end (in both success and failure paths). The scheduler reads the request
    body, sees `run_id`, and now records the row as `status="running"` until
    the callback arrives — so the UI never lies about completion state again.

Safe no-op if the run_id is missing (e.g. when the endpoint is hit manually
from curl rather than the scheduler). Failures of the callback itself are
swallowed: callback noise must not mask the underlying task outcome.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)


def extract_run_id(payload: dict[str, Any] | None) -> str | None:
    """Pull a scheduler run_id out of a request body (the scheduler always sends one)."""
    if not isinstance(payload, dict):
        return None
    val = payload.get("run_id")
    if not val:
        return None
    return str(val)


async def notify_scheduler_complete(
    scheduler_url: str,
    run_id: str | None,
    *,
    status: str = "success",
    error: str | None = None,
    service_jwt: str = "",
) -> None:
    """POST scheduler/internal/runs/{run_id}/complete. Best-effort, no raises."""
    if not run_id or not scheduler_url:
        return
    headers = {"Authorization": f"Bearer {service_jwt}"} if service_jwt else {}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=10) as client:
            await client.post(
                f"{scheduler_url.rstrip('/')}/internal/runs/{run_id}/complete",
                json={"status": status, "error": error},
            )
    except Exception as exc:
        # Don't let callback noise mask the real job outcome
        log.warning("scheduler_callback failed run_id=%s err=%r", run_id, exc)


async def run_with_callback(
    coro_factory,
    *,
    scheduler_url: str,
    run_id: str | None,
    service_jwt: str = "",
) -> Any:
    """Run an async callable and notify the scheduler about the outcome.

    Use this as the body of a BackgroundTasks task so the response can return
    202 immediately while the actual work — and its scheduler-callback — happen
    after the response is flushed.

        @router.post("/refresh", status_code=202)
        async def trigger_refresh(body: dict, bg: BackgroundTasks, request: Request):
            run_id = extract_run_id(body)
            jwt = getattr(request.app.state, "service_jwt", "")
            bg.add_task(
                run_with_callback,
                lambda: do_the_work(),
                scheduler_url=settings.scheduler_url,
                run_id=run_id,
                service_jwt=jwt,
            )
            return {"status": "running", "run_id": run_id}
    """
    try:
        result = await coro_factory()
        await notify_scheduler_complete(
            scheduler_url, run_id, status="success", service_jwt=service_jwt,
        )
        return result
    except Exception as exc:
        await notify_scheduler_complete(
            scheduler_url,
            run_id,
            status="failed",
            error=repr(exc)[:500],
            service_jwt=service_jwt,
        )
        raise
