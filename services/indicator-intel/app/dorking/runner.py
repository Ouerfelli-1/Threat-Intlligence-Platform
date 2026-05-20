"""Dork run orchestrator.

Walks the catalog for a target, fires each dork through Google CSE
(primary) with DDG (fallback) when Google quota-exceeds. Persists one
DorkRun row and one DorkFinding per (de-duplicated) result.

Persistence shape:
  DorkRun     ─ summary row: which target, which categories, which
                backend ACTUALLY served the bulk of queries, total
                findings, success/degraded/failed.
  DorkFinding ─ per-result row: which dork query surfaced the link,
                title, url, snippet, source backend (google|duckduckgo).

We dedupe by (category, url) within a run — the same link surfacing
in two different dorks of the same category is noise. Across categories
we keep duplicates because the context matters (e.g. a paste site URL
appearing under both paste_sites AND github_leaks is two separate
findings).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.dorking.catalog import build_dorks
from app.dorking.duckduckgo import DuckDuckGoUnavailable
from app.dorking.duckduckgo import search as ddg_search
from app.dorking.google import GoogleAuthError, GoogleRateLimited
from app.dorking.google import search as google_search
from app.models import DorkFinding, DorkRun

log = logging.getLogger(__name__)


@dataclass
class DorkResult:
    category: str
    dork: str
    title: str
    url: str
    snippet: str
    source: str  # "google" | "duckduckgo"


async def run_dorks(
    *,
    session: AsyncSession,
    target: str,
    target_type: str,
    categories: list[str] | None,
    limit_per_dork: int = 5,
    google_api_key: str | None = None,
    google_cse_id: str | None = None,
) -> DorkRun:
    """Execute the catalog, persist, return the DorkRun row.

    Backend selection:
      - If google_api_key + cse_id present, Google CSE first.
      - On per-query GoogleRateLimited, drop to DDG for that query.
      - On GoogleAuthError, give up on Google for the whole run and
        switch to DDG-only — bad key surfaces in run.error_detail.
      - If DDG is unavailable (lib not installed AND no Google), the
        run ends with status=failed and a clear error.
    """
    started_at = datetime.now(timezone.utc)
    run_id = uuid.uuid4()

    # Build the dork list once. catalog.build_dorks resolves placeholders.
    try:
        dork_list = build_dorks(target, target_type, categories)  # type: ignore[arg-type]
    except ValueError as exc:
        run = DorkRun(
            id=run_id, target=target, target_type=target_type,
            categories=categories or [], backend="none", status="failed",
            total_findings=0, error_detail=str(exc),
            started_at=started_at, finished_at=datetime.now(timezone.utc),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run

    # Track which backend(s) served — drives the DorkRun.backend column.
    google_ok = bool(google_api_key and google_cse_id)
    google_dead = not google_ok  # once True, stop trying Google for this run
    counts = {"google": 0, "duckduckgo": 0, "skipped": 0}

    deduped: set[tuple[str, str]] = set()  # (category, url)
    findings: list[DorkResult] = []
    notes: list[str] = []

    for category, dork in dork_list:
        # Try Google first while it's healthy.
        if not google_dead:
            try:
                gh = await google_search(
                    api_key=google_api_key or "", cse_id=google_cse_id or "",
                    query=dork, limit=limit_per_dork,
                )
                for r in gh:
                    key = (category, r.url)
                    if key in deduped:
                        continue
                    deduped.add(key)
                    findings.append(DorkResult(
                        category=category, dork=dork,
                        title=r.title, url=r.url, snippet=r.snippet,
                        source="google",
                    ))
                counts["google"] += 1
                continue  # success on this dork via Google — skip DDG
            except GoogleRateLimited:
                # Don't kill the whole run; switch to DDG for this query
                # but try Google again on the next (some quotas reset
                # mid-cycle). If we hit it twice in a row though, give up.
                notes.append(f"google_quota_on:{dork[:80]}")
                # Fall through to DDG for this query.
            except GoogleAuthError as exc:
                google_dead = True
                notes.append(f"google_auth_failed: {str(exc)[:200]}")
                # Fall through to DDG for this query.

        # DDG branch — either Google is dead, this query hit quota, or
        # Google wasn't configured in the first place.
        try:
            dh = await ddg_search(query=dork, limit=limit_per_dork)
        except DuckDuckGoUnavailable as exc:
            # Lib not installed. If Google is also dead we can't continue.
            notes.append(f"ddg_unavailable: {str(exc)[:200]}")
            counts["skipped"] += 1
            continue
        for r in dh:
            key = (category, r.url)
            if key in deduped:
                continue
            deduped.add(key)
            findings.append(DorkResult(
                category=category, dork=dork,
                title=r.title, url=r.url, snippet=r.snippet,
                source="duckduckgo",
            ))
        counts["duckduckgo"] += 1

    # Backend label captures the dominant source.
    if counts["google"] and counts["duckduckgo"]:
        backend = "mixed"
    elif counts["google"]:
        backend = "google"
    elif counts["duckduckgo"]:
        backend = "duckduckgo"
    else:
        backend = "none"

    # Status decides on (a) did we run anything and (b) was the run
    # full-service or limped through.
    if not findings and counts["skipped"] == len(dork_list):
        status = "failed"
    elif notes:
        status = "degraded"
    else:
        status = "success"

    finished_at = datetime.now(timezone.utc)
    run = DorkRun(
        id=run_id, target=target, target_type=target_type,
        categories=categories or [], backend=backend, status=status,
        total_findings=len(findings),
        error_detail="; ".join(notes)[:2000] if notes else None,
        started_at=started_at, finished_at=finished_at,
    )
    session.add(run)
    # flush so the FK works for the children
    await session.flush()

    for f in findings:
        session.add(DorkFinding(
            id=uuid.uuid4(),
            run_id=run.id,
            dork=f.dork, category=f.category,
            title=f.title[:512], url=f.url[:2048],
            snippet=f.snippet[:2048], source=f.source,
        ))
    await session.commit()
    await session.refresh(run)
    log.info(
        "dork_run target=%r type=%s backend=%s status=%s findings=%d "
        "google_q=%d ddg_q=%d notes=%d",
        target, target_type, backend, status, len(findings),
        counts["google"], counts["duckduckgo"], len(notes),
    )
    return run
