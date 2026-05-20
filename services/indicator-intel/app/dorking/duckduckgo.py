"""DuckDuckGo fallback adapter.

Uses the `ddgs` library (community successor to `duckduckgo-search`).
The library hits DDG's HTML / lite endpoints and parses results — no API
key required, but rate-limited by IP (~50 queries before a soft block).

If DDG blocks us we return [] for that query; the runner records the
degraded status but doesn't fail the whole investigation.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


class DuckDuckGoUnavailable(Exception):
    """DDG library not installed or blocking the IP."""


@dataclass
class DuckResult:
    title: str
    url: str
    snippet: str


async def search(
    *,
    query: str,
    limit: int = 5,
    timeout: float = 10.0,
) -> list[DuckResult]:
    """Run one DDG search, return up to `limit` results.

    The ddgs library is sync — we run it in a thread to keep the FastAPI
    event loop responsive. Failures are swallowed and turned into [] so a
    single dork's block doesn't abort the run.
    """
    try:
        # Imported here so the service still boots when the lib isn't
        # installed yet (the runner detects this and stays Google-only).
        from ddgs import DDGS  # type: ignore
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # type: ignore  # older name
        except ImportError as exc:
            raise DuckDuckGoUnavailable(
                "ddgs / duckduckgo-search not installed; "
                "add ddgs to pyproject.toml dependencies"
            ) from exc

    def _blocking_query() -> list[DuckResult]:
        try:
            with DDGS(timeout=timeout) as d:
                # The library's .text() returns one dict per hit:
                #   {title, href, body}
                raw = list(d.text(query, max_results=limit))
            return [
                DuckResult(
                    title=r.get("title") or "",
                    url=r.get("href") or r.get("url") or "",
                    snippet=r.get("body") or r.get("snippet") or "",
                )
                for r in raw
                if r.get("href") or r.get("url")
            ]
        except Exception as exc:
            log.warning("ddg_query_failed query=%r err=%s",
                        query, str(exc)[:160])
            return []

    return await asyncio.to_thread(_blocking_query)
