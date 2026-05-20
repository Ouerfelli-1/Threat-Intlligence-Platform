"""Google Custom Search adapter.

Requires:
  GOOGLE_API_KEY  — billing/quota key from console.cloud.google.com
  GOOGLE_CSE_ID   — CSE id from programmablesearchengine.google.com
                    (configured to search the entire web)

Free tier: 100 queries/day. We surface that 429 cleanly so the runner can
fall back to DuckDuckGo for the rest of the run.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)

_API_URL = "https://www.googleapis.com/customsearch/v1"


class GoogleRateLimited(Exception):
    """Quota exceeded or rate-limited. Caller should fall back to DDG."""


class GoogleAuthError(Exception):
    """API key / CSE id missing or rejected."""


@dataclass
class GoogleResult:
    title: str
    url: str
    snippet: str


async def search(
    *,
    api_key: str,
    cse_id: str,
    query: str,
    limit: int = 5,
    timeout: float = 10.0,
) -> list[GoogleResult]:
    """Run one CSE query, return up to `limit` results.

    Raises GoogleRateLimited on 429 (quota). Raises GoogleAuthError on
    400/403 with a clear "key invalid" body. Other errors return [].
    """
    if not api_key or not cse_id:
        raise GoogleAuthError("missing GOOGLE_API_KEY or GOOGLE_CSE_ID")

    params = {
        "key": api_key,
        "cx": cse_id,
        "q": query,
        "num": min(max(limit, 1), 10),  # CSE caps at 10 per page
    }
    async with httpx.AsyncClient(timeout=timeout) as c:
        resp = await c.get(_API_URL, params=params)

    if resp.status_code == 429:
        # Daily quota burned. Logged at the call site so callers can decide
        # to fall back; not an exception at the runner level.
        raise GoogleRateLimited(f"Google CSE quota exhausted (429); body={resp.text[:200]}")

    if resp.status_code == 403:
        # 403 + dailyLimitExceeded means quota; otherwise key/cse mismatch.
        body = resp.text
        if "dailyLimitExceeded" in body or "rateLimitExceeded" in body:
            raise GoogleRateLimited(f"Google CSE rate-limited (403); body={body[:200]}")
        raise GoogleAuthError(f"Google CSE rejected request: {body[:200]}")

    if resp.status_code == 400:
        # Bad query (rare with our catalog) — return empty instead of failing
        # the whole run.
        log.warning("google_cse_bad_request query=%r body=%s", query, resp.text[:200])
        return []

    if resp.status_code != 200:
        log.warning("google_cse_non_200 status=%d query=%r body=%s",
                    resp.status_code, query, resp.text[:200])
        return []

    data = resp.json()
    items = data.get("items") or []
    return [
        GoogleResult(
            title=item.get("title") or "",
            url=item.get("link") or "",
            snippet=item.get("snippet") or "",
        )
        for item in items
        if item.get("link")
    ][:limit]
