import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tip_common.logging_setup import get_logger
from tip_http import build_resilient_client, fetch_with_resilience
from tip_source_health import SourceHealthRepository

from app.models import CVE

logger = get_logger("vuln.nvd")

PAGE_SIZE = 2000


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _severity_from_score(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    if score > 0:
        return "low"
    return "none"


def _normalize_cve(item: dict[str, Any]) -> dict[str, Any] | None:
    cve = item.get("cve") or {}
    cve_id = cve.get("id")
    if not cve_id:
        return None

    descriptions = cve.get("descriptions") or []
    description = next(
        (d["value"] for d in descriptions if d.get("lang") == "en"),
        descriptions[0]["value"] if descriptions else None,
    )

    score = None
    vector = None
    metrics = cve.get("metrics") or {}
    for key in ("cvssMetricV31", "cvssMetricV30"):
        m = (metrics.get(key) or [{}])[0].get("cvssData") or {}
        if m:
            score = float(m.get("baseScore")) if m.get("baseScore") is not None else None
            vector = m.get("vectorString")
            break

    cwes = []
    for w in cve.get("weaknesses") or []:
        for d in w.get("description") or []:
            if d.get("lang") == "en" and d.get("value"):
                cwes.append(d["value"])

    products = {}
    for cfg in cve.get("configurations") or []:
        for node in cfg.get("nodes") or []:
            for m in node.get("cpeMatch") or []:
                if m.get("vulnerable") and m.get("criteria"):
                    products.setdefault("cpes", []).append(m["criteria"])

    references = [r["url"] for r in (cve.get("references") or []) if r.get("url")]

    return {
        "cve_id": cve_id,
        "published_at": _parse_dt(cve.get("published")),
        "last_modified_at": _parse_dt(cve.get("lastModified")),
        "description": description,
        "cvss_v3_score": score,
        "cvss_v3_vector": vector,
        "severity": _severity_from_score(score),
        "cwe": cwes,
        "affected_products": products,
        "references": references,
    }


async def _fetch_page(base_url: str, params: dict, api_key: str | None) -> dict:
    headers = {"User-Agent": "TIP-VulnIntel/0.1"}
    if api_key:
        headers["apiKey"] = api_key
    async with build_resilient_client() as client:
        resp = await client.client.get(base_url, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def sync_recent_cves(
    *,
    session: AsyncSession,
    base_url: str,
    api_key: str | None,
    health: SourceHealthRepository,
    days_back: int = 7,
) -> tuple[int, int, int]:
    """Pull CVEs modified within the last `days_back` days. Returns (seen, added, updated)."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)
    seen = added = updated = 0

    page = 0
    while True:
        params = {
            "lastModStartDate": start.isoformat(),
            "lastModEndDate": end.isoformat(),
            "resultsPerPage": PAGE_SIZE,
            "startIndex": page * PAGE_SIZE,
        }
        sleep_seconds = 0.6 if api_key else 6.0

        result = await fetch_with_resilience(
            "nvd",
            lambda: _fetch_page(base_url, params, api_key),
            health=health,
        )
        if not result.success or result.value is None:
            break

        data = result.value
        vulns = data.get("vulnerabilities") or []
        seen += len(vulns)
        for v in vulns:
            payload = _normalize_cve(v)
            if payload is None:
                continue
            stmt = (
                insert(CVE)
                .values(**payload)
                .on_conflict_do_update(
                    index_elements=["cve_id"],
                    set_={
                        "last_modified_at": payload["last_modified_at"],
                        "description": payload["description"],
                        "cvss_v3_score": payload["cvss_v3_score"],
                        "cvss_v3_vector": payload["cvss_v3_vector"],
                        "severity": payload["severity"],
                        "cwe": payload["cwe"],
                        "affected_products": payload["affected_products"],
                        "references": payload["references"],
                        "fetched_at": datetime.now(timezone.utc),
                    },
                )
                .returning(CVE.cve_id)
            )
            existing = await session.scalar(select(CVE.cve_id).where(CVE.cve_id == payload["cve_id"]))
            await session.execute(stmt)
            if existing is None:
                added += 1
            else:
                updated += 1
        await session.commit()

        total_results = int(data.get("totalResults") or 0)
        if (page + 1) * PAGE_SIZE >= total_results or not vulns:
            break
        page += 1
        await asyncio.sleep(sleep_seconds)

    return seen, added, updated


async def backfill_cves_by_id(
    *,
    session: AsyncSession,
    base_url: str,
    api_key: str | None,
    health: SourceHealthRepository,
    cve_ids: list[str],
    sleep_seconds: float | None = None,
) -> tuple[int, int, int]:
    """Pull individual CVE records from NVD by `cveId`.

    Used by /refresh/kev-backfill — the incremental NVD pull only covers a
    `lastModified` window, so CVEs older than the window (or CVEs published
    before we first booted) are missing from our DB. KEV references many of
    those (CISA includes Heartbleed, Log4Shell, etc.). Without backfill the
    "exploited only" filter returns ~1% of what it should because the
    `cves x kev` INNER JOIN drops every KEV row whose CVE we never fetched.

    NVD rate limits:
      - with api_key: 50 req / 30s   -> 0.6s sleep between calls is safe
      - without:       5 req / 30s   -> 6.0s sleep (1580 ids ~= 158 min)

    Returns (seen, added, updated). Idempotent — upserts on cve_id PK.
    """
    if not cve_ids:
        return 0, 0, 0

    # Auto-pace per the rate limit unless caller overrode.
    if sleep_seconds is None:
        sleep_seconds = 0.6 if api_key else 6.0

    seen = added = updated = 0
    for i, cve_id in enumerate(cve_ids):
        params = {"cveId": cve_id}
        result = await fetch_with_resilience(
            "nvd-backfill",
            lambda p=params: _fetch_page(base_url, p, api_key),
            health=health,
        )
        if not result.success or result.value is None:
            # tip_http already updated source_health.consecutive_failures.
            # Keep going — a single failed CVE shouldn't abort the batch.
            await asyncio.sleep(sleep_seconds)
            continue

        vulns = result.value.get("vulnerabilities") or []
        seen += len(vulns)
        for v in vulns:
            payload = _normalize_cve(v)
            if payload is None:
                continue
            existing = await session.scalar(select(CVE.cve_id).where(CVE.cve_id == payload["cve_id"]))
            stmt = (
                insert(CVE)
                .values(**payload)
                .on_conflict_do_update(
                    index_elements=["cve_id"],
                    set_={
                        "last_modified_at": payload["last_modified_at"],
                        "description":      payload["description"],
                        "cvss_v3_score":    payload["cvss_v3_score"],
                        "cvss_v3_vector":   payload["cvss_v3_vector"],
                        "severity":         payload["severity"],
                        "cwe":              payload["cwe"],
                        "affected_products": payload["affected_products"],
                        "references":       payload["references"],
                        "fetched_at":       datetime.now(timezone.utc),
                    },
                )
            )
            await session.execute(stmt)
            if existing is None:
                added += 1
            else:
                updated += 1

        # Commit periodically so a long backfill is recoverable.
        if (i + 1) % 25 == 0:
            await session.commit()

        await asyncio.sleep(sleep_seconds)

    await session.commit()
    return seen, added, updated
