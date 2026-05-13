"""Passive investigation pipeline.

All sources run concurrently via asyncio.gather. Missing API keys or unreachable
sources are silently skipped so the investigation still completes with partial data.
"""
import asyncio
from typing import Any

import httpx
from pydantic import BaseModel

from tip_ai import OpenRouterClient, generate_structured
from tip_schemas import normalize_indicator

from app.settings import Settings

_SYSTEM_PROMPT = """
You are a threat intelligence analyst performing a passive investigation of a network indicator (IP or domain).

You will receive raw findings collected from multiple passive sources. Your task is to synthesize these into a
structured verdict:
- verdict: one of "benign", "suspicious", "malicious", "unknown"
- confidence: 0.0-1.0 (your confidence in the verdict)
- risk_score: 0-100 (composite risk score for prioritization)
- summary: 2-4 sentence analyst-quality summary of findings and rationale
- ttps: MITRE ATT&CK technique IDs observed (if any)
- related_actors: named threat actors this indicator is attributed to (if any)
- recommended_actions: concrete operational steps for the SOC team
- tags: short labels (e.g. "c2", "tor-exit", "cdn", "phishing", "botnet")

Base your verdict on: IP geolocation, open ports/services, CVE exposure (Shodan), IOC database matches,
TI actor attribution, known-malicious ASNs, and article mentions. When uncertain, use "unknown" with a lower
confidence score rather than guessing.
""".strip()


class InvestigationVerdict(BaseModel):
    verdict: str
    confidence: float
    risk_score: int
    summary: str
    ttps: list[str] = []
    related_actors: list[str] = []
    recommended_actions: list[str] = []
    tags: list[str] = []


async def _ip_api(ip: str, client: httpx.AsyncClient) -> dict:
    try:
        fields = "country,regionName,city,lat,lon,isp,org,as,query"
        resp = await client.get(f"http://ip-api.com/json/{ip}?fields={fields}", timeout=10)
        if resp.status_code == 200:
            return {"ip_api": resp.json()}
    except Exception:
        pass
    return {}


async def _shodan(ip: str, api_key: str, client: httpx.AsyncClient) -> dict:
    if not api_key:
        return {}
    try:
        resp = await client.get(
            f"https://api.shodan.io/shodan/host/{ip}",
            params={"key": api_key},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "shodan": {
                    "ports": data.get("ports", []),
                    "vulns": list(data.get("vulns", {}).keys()),
                    "hostnames": data.get("hostnames", []),
                    "country_name": data.get("country_name"),
                    "org": data.get("org"),
                    "isp": data.get("isp"),
                    "asn": data.get("asn"),
                }
            }
    except Exception:
        pass
    return {}


async def _crtsh(value: str, client: httpx.AsyncClient) -> dict:
    try:
        resp = await client.get(
            "https://crt.sh/",
            params={"q": value, "output": "json"},
            timeout=15,
        )
        if resp.status_code == 200:
            entries = resp.json()
            names = list({e.get("name_value", "") for e in entries if e.get("name_value")})
            return {"crtsh": {"subdomains": names[:200]}}
    except Exception:
        pass
    return {}


async def _rdap(value: str) -> dict:
    try:
        import whois as _whois
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _whois.whois, value)
        return {
            "whois": {
                "registrar": result.registrar,
                "creation_date": str(result.creation_date) if result.creation_date else None,
                "expiration_date": str(result.expiration_date) if result.expiration_date else None,
                "name_servers": list(result.name_servers) if result.name_servers else [],
            }
        }
    except Exception:
        pass
    return {}


async def _passive_dns(value: str, client: httpx.AsyncClient) -> dict:
    subdomains: set[str] = set()
    try:
        resp = await client.get(
            f"https://api.hackertarget.com/hostsearch/?q={value}",
            timeout=10,
        )
        if resp.status_code == 200 and "error" not in resp.text.lower():
            for line in resp.text.splitlines():
                parts = line.split(",")
                if parts:
                    subdomains.add(parts[0].strip())
    except Exception:
        pass
    return {"passive_dns": list(subdomains)[:100]} if subdomains else {}


async def _ioc_lookup(value: str, ioc_type: str, ioc_url: str, client: httpx.AsyncClient) -> dict:
    try:
        resp = await client.post(
            f"{ioc_url}/indicators/lookup",
            json={"indicators": [{"type": ioc_type, "value": value}]},
            timeout=10,
        )
        if resp.status_code == 200:
            return {"local_iocs": resp.json()}
    except Exception:
        pass
    return {}


async def _actor_search(value: str, actors_url: str, client: httpx.AsyncClient) -> dict:
    try:
        resp = await client.get(f"{actors_url}/actors", params={"q": value}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                return {"related_actors": data[:5]}
    except Exception:
        pass
    return {}


async def _article_search(value: str, news_url: str, client: httpx.AsyncClient) -> dict:
    try:
        resp = await client.get(f"{news_url}/articles", params={"q": value, "page_size": 5}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                return {"related_articles": [{"id": str(a.get("id")), "title": a.get("title")} for a in data[:5]]}
    except Exception:
        pass
    return {}


async def _intelowl(value: str, indicator_type: str, intelowl_url: str, api_key: str, client: httpx.AsyncClient) -> dict:
    if not intelowl_url or not api_key:
        return {}
    try:
        classification = "ip" if indicator_type == "ip" else "domain"
        resp = await client.post(
            f"{intelowl_url}/api/analyze_observable",
            json={"observable_name": value, "observable_classification": classification, "analyzers_requested": []},
            headers={"Authorization": f"Token {api_key}"},
            timeout=20,
        )
        if resp.status_code in (200, 201):
            return {"intelowl": resp.json()}
    except Exception:
        pass
    return {}


async def run_investigation(
    indicator_type: str,
    raw_value: str,
    settings: Settings,
    service_jwt: str = "",
) -> dict[str, Any]:
    normalized = normalize_indicator(indicator_type, raw_value)
    headers = {"Authorization": f"Bearer {service_jwt}"} if service_jwt else {}

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        tasks: list[asyncio.Task] = []

        if indicator_type == "ip":
            tasks.append(asyncio.create_task(_ip_api(normalized, client)))
            tasks.append(asyncio.create_task(_shodan(normalized, settings.shodan_api_key, client)))
        else:
            tasks.append(asyncio.create_task(_passive_dns(normalized, client)))

        tasks.append(asyncio.create_task(_crtsh(normalized, client)))
        tasks.append(asyncio.create_task(_rdap(normalized)))
        tasks.append(asyncio.create_task(_ioc_lookup(normalized, indicator_type, settings.ioc_collector_url, client)))
        tasks.append(asyncio.create_task(_actor_search(normalized, settings.threat_actors_url, client)))
        tasks.append(asyncio.create_task(_article_search(normalized, settings.news_collector_url, client)))
        tasks.append(asyncio.create_task(_intelowl(normalized, indicator_type, settings.intelowl_url, settings.intelowl_api_key, client)))

        results = await asyncio.gather(*tasks, return_exceptions=True)

    merged: dict[str, Any] = {}
    for r in results:
        if isinstance(r, dict):
            merged.update(r)
    return merged


async def synthesize_verdict(
    indicator_type: str,
    raw_value: str,
    raw_findings: dict[str, Any],
    ai_client: OpenRouterClient,
) -> dict[str, Any]:
    verdict = await generate_structured(
        ai_client,
        system_prompt=_SYSTEM_PROMPT,
        user_payload={
            "indicator_type": indicator_type,
            "value": raw_value,
            "findings": raw_findings,
        },
        schema=InvestigationVerdict,
    )
    return verdict.model_dump()
