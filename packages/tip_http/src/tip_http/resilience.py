import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

import httpx

from tip_common.logging_setup import get_logger

logger = get_logger("tip_http.resilience")

T = TypeVar("T")


class CircuitOpen(Exception):
    pass


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 1.0
    backoff: float = 2.0
    jitter: float = 0.25


@dataclass
class SourceCallResult(Generic[T]):
    source: str
    success: bool
    value: T | None
    error: str | None
    attempts: int
    duration_ms: int
    http_status: int | None


class HealthStore(Protocol):
    async def is_open(self, source: str) -> bool: ...
    async def mark_success(self, source: str, http_status: int | None = None) -> None: ...
    async def mark_failure(
        self, source: str, error: str, http_status: int | None = None
    ) -> None: ...


def _is_retryable_status(status: int) -> bool:
    return status >= 500 or status == 429


async def _attempt_with_retries(
    fn: Callable[[], Awaitable[T]],
    policy: RetryPolicy,
) -> tuple[T | None, str | None, int | None, int]:
    last_error: str | None = None
    http_status: int | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            value = await fn()
            return value, None, http_status, attempt
        except httpx.HTTPStatusError as e:
            http_status = e.response.status_code
            last_error = f"http {http_status}: {e}"
            if not _is_retryable_status(http_status):
                return None, last_error, http_status, attempt
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as e:
            last_error = f"{type(e).__name__}: {e}"
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            return None, last_error, http_status, attempt
        if attempt < policy.max_attempts:
            delay = policy.base_delay * (policy.backoff ** (attempt - 1))
            delay *= 1 + random.uniform(-policy.jitter, policy.jitter)
            await asyncio.sleep(delay)
    return None, last_error, http_status, policy.max_attempts


async def fetch_with_resilience(
    source: str,
    fn: Callable[[], Awaitable[T]],
    *,
    health: HealthStore | None = None,
    policy: RetryPolicy | None = None,
) -> SourceCallResult[T]:
    policy = policy or RetryPolicy()
    loop = asyncio.get_event_loop()
    started = loop.time()

    if health is not None and await health.is_open(source):
        return SourceCallResult(
            source=source,
            success=False,
            value=None,
            error="circuit_open",
            attempts=0,
            duration_ms=0,
            http_status=None,
        )

    value, error, http_status, attempts = await _attempt_with_retries(fn, policy)
    duration_ms = int((loop.time() - started) * 1000)

    if value is not None:
        if health is not None:
            await health.mark_success(source, http_status)
        logger.debug(
            "source_call_ok", source=source, attempts=attempts, duration_ms=duration_ms
        )
        return SourceCallResult(
            source=source,
            success=True,
            value=value,
            error=None,
            attempts=attempts,
            duration_ms=duration_ms,
            http_status=http_status,
        )

    if health is not None:
        await health.mark_failure(source, error or "unknown", http_status)
    logger.warning(
        "source_call_failed",
        source=source,
        error=error,
        attempts=attempts,
        http_status=http_status,
        duration_ms=duration_ms,
    )
    return SourceCallResult(
        source=source,
        success=False,
        value=None,
        error=error,
        attempts=attempts,
        duration_ms=duration_ms,
        http_status=http_status,
    )
