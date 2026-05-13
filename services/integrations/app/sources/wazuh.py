"""
Wazuh SIEM integration.
Auth: POST /security/user/authenticate with Basic → JWT → cached 1h.
Pulls alerts and agent list, upserts by alert_id.
"""
import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tip_http import build_resilient_client
from tip_source_health import SourceHealthRepository

from app.models import WazuhAgent, WazuhAlert

log = logging.getLogger(__name__)
SOURCE_NAME = "wazuh"

_wazuh_jwt_cache: dict = {}


async def _get_wazuh_jwt(base_url: str, username: str, password: str, client: httpx.AsyncClient) -> str:
    cached = _wazuh_jwt_cache.get("token")
    if cached and _wazuh_jwt_cache.get("expires_at", 0) > datetime.now(timezone.utc).timestamp():
        return cached

    resp = await client.post(
        f"{base_url}/security/user/authenticate",
        auth=(username, password),
        timeout=15,
    )
    resp.raise_for_status()
    token = resp.json()["data"]["token"]
    _wazuh_jwt_cache["token"] = token
    _wazuh_jwt_cache["expires_at"] = datetime.now(timezone.utc).timestamp() + 3500  # 1h - buffer
    return token


async def sync_wazuh(
    session: AsyncSession,
    health: SourceHealthRepository,
    base_url: str,
    username: str,
    password: str,
    page_limit: int = 500,
) -> dict:
    if not base_url or not username or not password:
        log.info("wazuh skipped: no credentials configured")
        return {"alerts": 0, "agents": 0}

    if await health.is_open(SOURCE_NAME):
        return {"alerts": 0, "agents": 0}

    try:
        async with build_resilient_client(base_url=base_url) as client:
            token = await _get_wazuh_jwt(base_url, username, password, client)
            headers = {"Authorization": f"Bearer {token}"}

            alerts_count = await _sync_alerts(session, client, headers, page_limit)
            agents_count = await _sync_agents(session, client, headers)

        await session.commit()
        await health.mark_success(SOURCE_NAME)
        log.info("wazuh synced alerts=%d agents=%d", alerts_count, agents_count)
        return {"alerts": alerts_count, "agents": agents_count}

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            _wazuh_jwt_cache.clear()
        log.error("wazuh sync error=%s", exc)
        await health.mark_failure(SOURCE_NAME, str(exc), http_status=exc.response.status_code)
        return {"alerts": 0, "agents": 0}
    except Exception as exc:
        log.error("wazuh sync error=%s", exc)
        await health.mark_failure(SOURCE_NAME, str(exc))
        return {"alerts": 0, "agents": 0}


async def _sync_alerts(
    session: AsyncSession, client: httpx.AsyncClient, headers: dict, limit: int
) -> int:
    resp = await client.get(
        "/alerts",
        headers=headers,
        params={"limit": limit, "sort": "-timestamp"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    alerts = data.get("data", {}).get("affected_items", [])

    count = 0
    for alert in alerts:
        alert_id = alert.get("id", "")
        if not alert_id:
            continue
        ts_raw = alert.get("timestamp")
        ts = None
        if ts_raw:
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except Exception:
                pass

        stmt = insert(WazuhAlert.__table__).values(
            alert_id=alert_id,
            agent_id=alert.get("agent", {}).get("id"),
            agent_name=alert.get("agent", {}).get("name"),
            rule_id=str(alert.get("rule", {}).get("id", "")),
            rule_description=alert.get("rule", {}).get("description", "")[:1024],
            severity=int(alert.get("rule", {}).get("level", 0)),
            timestamp=ts,
            raw=alert,
        ).on_conflict_do_update(
            constraint="wazuh_alerts_pkey",
            set_={"raw": alert, "timestamp": ts, "severity": int(alert.get("rule", {}).get("level", 0))},
        )
        await session.execute(stmt)
        count += 1

    return count


async def _sync_agents(session: AsyncSession, client: httpx.AsyncClient, headers: dict) -> int:
    resp = await client.get("/agents", headers=headers, params={"limit": 500}, timeout=30)
    resp.raise_for_status()
    agents = resp.json().get("data", {}).get("affected_items", [])

    count = 0
    for agent in agents:
        agent_id = agent.get("id", "")
        if not agent_id:
            continue
        last_seen_raw = agent.get("lastKeepAlive")
        last_seen = None
        if last_seen_raw:
            try:
                last_seen = datetime.fromisoformat(last_seen_raw.replace("Z", "+00:00"))
            except Exception:
                pass

        stmt = insert(WazuhAgent.__table__).values(
            agent_id=agent_id,
            hostname=agent.get("name"),
            ip=agent.get("ip"),
            os=agent.get("os", {}).get("name"),
            version=agent.get("version"),
            last_seen=last_seen,
            status=agent.get("status", "active"),
            raw=agent,
        ).on_conflict_do_update(
            constraint="wazuh_agents_pkey",
            set_={"hostname": agent.get("name"), "ip": agent.get("ip"), "status": agent.get("status", "active"), "last_seen": last_seen, "raw": agent},
        )
        await session.execute(stmt)
        count += 1

    return count
