"""HTTP fan-out context provider for the orchestrator.

Fetches data from all downstream services concurrently.
"""
import asyncio
from typing import Any

import httpx

from app.settings import Settings


class OrchestratorContextProvider:
    """Fetches context from all downstream services for AI synthesis."""

    def __init__(self, settings: Settings, service_jwt: str = "") -> None:
        self._settings = settings
        self._jwt = service_jwt

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._jwt}"} if self._jwt else {}

    async def company_profile(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(headers=self._headers(), timeout=10) as c:
                r = await c.get(f"{self._settings.cmdb_url}/profile/latest")
                if r.status_code == 200:
                    return r.json()
        except Exception:
            pass
        return {}

    async def related_actors(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(headers=self._headers(), timeout=10) as c:
                r = await c.get(f"{self._settings.threat_actors_url}/actors")
                if r.status_code == 200:
                    return r.json()[:20]
        except Exception:
            pass
        return []

    async def related_iocs(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            value = item.get("value") or item.get("normalized_value", "")
            if not value:
                return []
            async with httpx.AsyncClient(headers=self._headers(), timeout=10) as c:
                r = await c.post(
                    f"{self._settings.ioc_collector_url}/indicators/lookup",
                    json={"indicators": [{"type": "domain", "value": value}]},
                )
                if r.status_code == 200:
                    return r.json()[:25]
        except Exception:
            pass
        return []

    async def related_articles(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            q = item.get("title") or item.get("name") or item.get("cve_id", "")
            async with httpx.AsyncClient(headers=self._headers(), timeout=10) as c:
                r = await c.get(f"{self._settings.news_collector_url}/articles", params={"q": q, "page_size": 5})
                if r.status_code == 200:
                    return r.json()[:10]
        except Exception:
            pass
        return []


async def fetch_cves(settings: Settings, jwt: str) -> list[dict]:
    """Pull recent KEV + high-EPSS CVEs from vuln-intel."""
    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=15) as c:
            tasks = [
                c.get(f"{settings.vuln_intel_url}/cves", params={"kev": "true"}),
                c.get(f"{settings.vuln_intel_url}/cves", params={"epss_gte": "0.7"}),
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            seen: set[str] = set()
            cves: list[dict] = []
            for r in responses:
                if isinstance(r, Exception) or r.status_code != 200:
                    continue
                for cve in r.json():
                    cid = cve.get("cve_id", "")
                    if cid and cid not in seen:
                        seen.add(cid)
                        cves.append(cve)
            return cves[:50]
    except Exception:
        return []


async def fetch_actors(settings: Settings, jwt: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=15) as c:
            r = await c.get(f"{settings.threat_actors_url}/actors")
            if r.status_code == 200:
                return r.json()[:100]
    except Exception:
        pass
    return []


async def fetch_ransomware_victims(settings: Settings, jwt: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=10) as c:
            r = await c.get(f"{settings.threat_actors_url}/ransomware/victims")
            if r.status_code == 200:
                return r.json()[:50]
    except Exception:
        pass
    return []


async def fetch_wazuh_alerts(settings: Settings, jwt: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=10) as c:
            r = await c.get(f"{settings.integrations_url}/wazuh/alerts", params={"severity_gte": "4"})
            if r.status_code == 200:
                return r.json()[:200]
    except Exception:
        pass
    return []


async def fetch_company_profile(settings: Settings, jwt: str) -> dict:
    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=10) as c:
            r = await c.get(f"{settings.cmdb_url}/profile/latest")
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return {}


async def generate_flow_for_finding(finding_description: str, settings: Settings, jwt: str) -> dict:
    """Call flowviz to produce an attack flow for a single finding."""
    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=30) as c:
            r = await c.post(f"{settings.flowviz_url}/flows", json={"input": finding_description})
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return {}
