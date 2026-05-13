"""
HIBP (Have I Been Pwned) domain breach lookup.
Queries each public domain from CMDB profile and upserts results.
"""
import logging
from datetime import date
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_http import build_resilient_client
from tip_source_health import SourceHealthRepository

from app.models import HIBPBreach

log = logging.getLogger(__name__)

SOURCE_NAME = "hibp"
HIBP_BASE = "https://haveibeenpwned.com/api/v3"


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


async def _fetch_breaches_for_domain(
    client: httpx.AsyncClient, domain: str, api_key: str
) -> list[dict]:
    headers = {"hibp-api-key": api_key, "user-agent": "TIP-Platform/1.0"}
    try:
        resp = await client.get(
            f"{HIBP_BASE}/breacheddomain/{domain}",
            headers=headers,
            timeout=20,
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        # HIBP returns a dict of {account_name: [breach_names]}; we need breach details separately
        return list(resp.json().keys()) if isinstance(resp.json(), dict) else []
    except Exception as exc:
        log.warning("hibp domain=%s error=%s", domain, exc)
        return []


async def _fetch_breach_detail(
    client: httpx.AsyncClient, breach_name: str, api_key: str
) -> dict | None:
    headers = {"hibp-api-key": api_key, "user-agent": "TIP-Platform/1.0"}
    try:
        resp = await client.get(
            f"{HIBP_BASE}/breach/{breach_name}",
            headers=headers,
            timeout=20,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        log.warning("hibp breach_detail=%s error=%s", breach_name, exc)
        return None


async def sync_hibp(
    session: AsyncSession,
    health: SourceHealthRepository,
    api_key: str,
    cmdb_url: str,
    service_headers: dict,
) -> int:
    if not api_key:
        log.info("hibp skipped: no api key configured")
        return 0

    # is_open() == True means circuit breaker is open → skip.
    if await health.is_open(SOURCE_NAME):
        return 0

    # Get public domains from CMDB profile
    try:
        async with build_resilient_client(base_url=cmdb_url, headers=service_headers) as client:
            resp = await client.get("/profile/latest", timeout=10)
            resp.raise_for_status()
            profile = resp.json()
        domains: list[str] = profile.get("public_domains", []) or []
    except Exception as exc:
        log.warning("hibp cannot reach cmdb: %s", exc)
        domains = []

    if not domains:
        log.info("hibp no public domains in cmdb profile, skipping")
        return 0

    count = 0
    async with build_resilient_client(base_url=HIBP_BASE) as client:
        seen_breaches: set[str] = set()
        for domain in domains:
            breach_names = await _fetch_breaches_for_domain(client, domain, api_key)
            for bname in breach_names:
                if bname in seen_breaches:
                    continue
                seen_breaches.add(bname)
                detail = await _fetch_breach_detail(client, bname, api_key)
                if detail:
                    await _upsert_breach(session, detail)
                    count += 1

    try:
        await session.commit()
        await health.mark_success(SOURCE_NAME)
        log.info("hibp breaches_synced=%d", count)
    except Exception as exc:
        await session.rollback()
        await health.mark_failure(SOURCE_NAME, str(exc))

    return count


async def _upsert_breach(session: AsyncSession, data: dict) -> None:
    name = data.get("Name", "")
    if not name:
        return

    result = await session.execute(select(HIBPBreach).where(HIBPBreach.name == name))
    existing = result.scalar_one_or_none()

    values = {
        "breach_date": _parse_date(data.get("BreachDate")),
        "added_date": _parse_date(data.get("AddedDate")),
        "pwn_count": data.get("PwnCount", 0),
        "data_classes": data.get("DataClasses", []),
        "description": data.get("Description"),
        "is_verified": data.get("IsVerified", False),
        "is_sensitive": data.get("IsSensitive", False),
        "raw": data,
    }

    if existing:
        for k, v in values.items():
            setattr(existing, k, v)
    else:
        session.add(HIBPBreach(name=name, **values))
