"""Passive investigation pipeline (no AI in this module).

All sources run concurrently via asyncio.gather. Missing API keys or unreachable
sources are silently skipped so the investigation still completes with partial data.

Sources covered:
  - dns_records:     A / AAAA / MX / NS / TXT / CNAME / SOA (dnspython)
  - reverse_dns:     PTR record (for IPs)
  - ip_api:          ip-api.com free tier (no key needed)
  - shodan:          host details + ports + vulns (Shodan API key)
  - abuseipdb:       reputation + reports (AbuseIPDB key, optional)
  - crtsh:           certificate transparency subdomains
  - rdap / whois:    registrar, dates, name servers
  - passive_dns:     HackerTarget hostsearch
  - local_iocs:      lookup against our ioc-collector library
  - related_actors:  cross-reference against threat-actors library
  - related_articles: cross-reference against news-collector articles
  - intelowl:        if a self-hosted IntelOwl is configured

The AI-driven verdict synthesis lives in `synthesize_verdict` and is now
ONLY called when explicitly requested via the on-demand /synthesize endpoint.
The default investigation path never burns LLM tokens.
"""
from __future__ import annotations

import asyncio
import socket
from typing import Any

import httpx
from pydantic import BaseModel

from tip_ai import OpenRouterClient, generate_structured
from tip_schemas import normalize_indicator

from app.settings import Settings

# Optional dependency — fall back gracefully if dnspython isn't installed yet.
try:
    import dns.asyncresolver  # type: ignore
    import dns.resolver  # type: ignore

    _DNS_AVAILABLE = True
except Exception:  # pragma: no cover
    _DNS_AVAILABLE = False


_SYSTEM_PROMPT = """
You are a threat intelligence analyst reviewing a completed passive investigation
of a network indicator (IP or domain).

You will receive raw findings collected from multiple passive sources. Your task
is to synthesize these into a structured verdict:
- verdict: one of "benign", "suspicious", "malicious", "unknown"
- confidence: 0.0-1.0 (your confidence in the verdict)
- risk_score: 0-100 (composite risk score for prioritization)
- summary: 2-4 sentence analyst-quality summary of findings and rationale
- ttps: MITRE ATT&CK technique IDs observed (if any)
- related_actors: named threat actors this indicator is attributed to (if any)
- recommended_actions: concrete operational steps for the SOC team
- tags: short labels (e.g. "c2", "tor-exit", "cdn", "phishing", "botnet")

Base your verdict on: IP geolocation, DNS records, ASN, open ports/services,
CVE exposure (Shodan), AbuseIPDB reports, IOC database matches, threat-actor
attribution, ASN-reputation signals, and article mentions. When uncertain, use
"unknown" with a lower confidence score rather than guessing.
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


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def auto_detect_type(value: str) -> str:
    """Best-effort indicator-type inference from a raw value."""
    v = (value or "").strip()
    if not v:
        return "domain"
    # IPv4
    parts = v.split(".")
    if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        return "ip"
    # Hashes by hex length
    hex_only = all(c in "0123456789abcdefABCDEF" for c in v)
    if hex_only:
        if len(v) == 64:
            return "sha256"
        if len(v) == 40:
            return "sha1"
        if len(v) == 32:
            return "md5"
    if "://" in v:
        return "url"
    return "domain"


# ─────────────────────────────────────────────────────────────────────────────
# DNS lookups (dnspython)
# ─────────────────────────────────────────────────────────────────────────────

async def _dns_records(domain: str) -> dict:
    """A / AAAA / MX / NS / TXT / CNAME / SOA for a domain."""
    if not _DNS_AVAILABLE:
        return {}
    out: dict[str, list] = {}
    resolver = dns.asyncresolver.Resolver()
    resolver.timeout = 4
    resolver.lifetime = 5

    async def _one(rrtype: str) -> None:
        try:
            ans = await resolver.resolve(domain, rrtype)
            values: list[str] = []
            for r in ans:
                if rrtype == "MX":
                    values.append(f"{r.preference} {r.exchange.to_text().rstrip('.')}")
                else:
                    values.append(r.to_text().strip('"').rstrip("."))
            if values:
                out[rrtype.lower()] = values
        except Exception:
            pass

    await asyncio.gather(
        _one("A"), _one("AAAA"), _one("MX"), _one("NS"),
        _one("TXT"), _one("CNAME"), _one("SOA"),
        return_exceptions=True,
    )
    if not out:
        return {}
    return {"dns_records": out}


async def _reverse_dns(ip: str) -> dict:
    """PTR lookup (reverse DNS) for an IP. Runs in a worker thread to avoid
    blocking the event loop."""
    def _do() -> str | None:
        try:
            host, _, _ = socket.gethostbyaddr(ip)
            return host
        except Exception:
            return None

    try:
        host = await asyncio.get_event_loop().run_in_executor(None, _do)
        if host:
            return {"reverse_dns": host}
    except Exception:
        pass
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# External enrichment sources
# ─────────────────────────────────────────────────────────────────────────────

async def _ip_api(ip: str, client: httpx.AsyncClient) -> dict:
    try:
        fields = "country,countryCode,regionName,city,lat,lon,isp,org,as,asname,reverse,mobile,proxy,hosting,query"
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
                    "vulns": list(data.get("vulns", {}).keys()) if isinstance(data.get("vulns"), dict) else list(data.get("vulns", [])),
                    "hostnames": data.get("hostnames", []),
                    "country_name": data.get("country_name"),
                    "city": data.get("city"),
                    "org": data.get("org"),
                    "isp": data.get("isp"),
                    "asn": data.get("asn"),
                    "os": data.get("os"),
                    "tags": data.get("tags", []),
                    "last_update": data.get("last_update"),
                }
            }
    except Exception:
        pass
    return {}


async def _abuseipdb(ip: str, api_key: str, client: httpx.AsyncClient) -> dict:
    """AbuseIPDB v2: returns abuse confidence score + recent reports.
    Free tier allows 1000 checks/day with a registered key."""
    if not api_key:
        return {}
    try:
        resp = await client.get(
            "https://api.abuseipdb.com/api/v2/check",
            params={"ipAddress": ip, "maxAgeInDays": 90, "verbose": ""},
            headers={"Key": api_key, "Accept": "application/json"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = (resp.json() or {}).get("data") or {}
            return {
                "abuseipdb": {
                    "abuse_confidence_score": data.get("abuseConfidenceScore"),
                    "total_reports": data.get("totalReports"),
                    "last_reported_at": data.get("lastReportedAt"),
                    "country_code": data.get("countryCode"),
                    "usage_type": data.get("usageType"),
                    "isp": data.get("isp"),
                    "domain": data.get("domain"),
                    "is_whitelisted": data.get("isWhitelisted"),
                    "is_tor": data.get("isTor"),
                    "reports_sample": (data.get("reports") or [])[:5],
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
            names: set[str] = set()
            for e in entries:
                nv = e.get("name_value", "")
                for n in (nv or "").split("\n"):
                    n = n.strip().lower()
                    if n:
                        names.add(n)
            return {"crtsh": {"subdomains": sorted(names)[:200]}}
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
                "registrar": getattr(result, "registrar", None),
                "creation_date": str(result.creation_date) if getattr(result, "creation_date", None) else None,
                "expiration_date": str(result.expiration_date) if getattr(result, "expiration_date", None) else None,
                "name_servers": list(result.name_servers) if getattr(result, "name_servers", None) else [],
                "emails": (list(result.emails) if isinstance(getattr(result, "emails", None), list) else [str(result.emails)]) if getattr(result, "emails", None) else [],
                "country": getattr(result, "country", None),
                "org": getattr(result, "org", None),
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
    return {"passive_dns": sorted(subdomains)[:100]} if subdomains else {}


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
        resp = await client.get(
            f"{actors_url}/actors",
            params={"q": value, "limit": 5},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items") if isinstance(data, dict) else data
            if items:
                return {"related_actors": items[:5]}
    except Exception:
        pass
    return {}


async def _article_search(value: str, news_url: str, client: httpx.AsyncClient) -> dict:
    try:
        resp = await client.get(f"{news_url}/articles", params={"q": value, "limit": 5}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items") if isinstance(data, dict) else data
            if items:
                return {
                    "related_articles": [
                        {"id": str(a.get("id")), "title": a.get("title"), "url": a.get("url")}
                        for a in (items or [])[:5]
                    ]
                }
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


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

async def run_investigation(
    indicator_type: str,
    raw_value: str,
    settings: Settings,
    service_jwt: str = "",
) -> dict[str, Any]:
    """Runs ALL passive sources in parallel and returns a merged findings dict.
    No AI is invoked here — call `synthesize_verdict` separately if you want one."""
    # Defensive type resolution: callers occasionally pass 'auto'
    if indicator_type in (None, "", "auto"):
        indicator_type = auto_detect_type(raw_value)

    normalized = normalize_indicator(indicator_type, raw_value)
    headers = {"Authorization": f"Bearer {service_jwt}"} if service_jwt else {}
    abuseipdb_key = getattr(settings, "abuseipdb_api_key", "") or ""

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        tasks: list = []

        if indicator_type == "ip":
            tasks.append(asyncio.create_task(_ip_api(normalized, client)))
            tasks.append(asyncio.create_task(_shodan(normalized, settings.shodan_api_key, client)))
            tasks.append(asyncio.create_task(_reverse_dns(normalized)))
            tasks.append(asyncio.create_task(_abuseipdb(normalized, abuseipdb_key, client)))
        else:
            # Domain path: DNS records, passive DNS, then ip-api/shodan/abuseipdb on the resolved A record
            tasks.append(asyncio.create_task(_dns_records(normalized)))
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

        # Domain bonus: if we have an A-record, enrich the first IP with ip-api/shodan/abuseipdb/PTR
        if indicator_type != "ip":
            a_records = (merged.get("dns_records") or {}).get("a") or []
            if a_records:
                first_ip = a_records[0]
                ip_tasks = [
                    asyncio.create_task(_ip_api(first_ip, client)),
                    asyncio.create_task(_shodan(first_ip, settings.shodan_api_key, client)),
                    asyncio.create_task(_reverse_dns(first_ip)),
                    asyncio.create_task(_abuseipdb(first_ip, abuseipdb_key, client)),
                ]
                ip_results = await asyncio.gather(*ip_tasks, return_exceptions=True)
                ip_enrichment: dict[str, Any] = {}
                for r in ip_results:
                    if isinstance(r, dict):
                        ip_enrichment.update(r)
                if ip_enrichment:
                    merged["resolved_ip"] = first_ip
                    merged["resolved_ip_enrichment"] = ip_enrichment

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
