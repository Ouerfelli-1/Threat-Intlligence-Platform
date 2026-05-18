"""HTTP fan-out context provider for the orchestrator.

Fetches data from all downstream services concurrently.
"""
import asyncio
import re
from typing import Any

import httpx

from app.settings import Settings


# Common English words that aren't useful as search terms. Kept small on
# purpose — over-aggressive stop-lists kill recall ("attack", "domain", "ip"
# are real signals for us). Add sparingly and only when a real false-match
# appears in logs.
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "have", "has", "had", "having",
    "in", "on", "of", "for", "to", "from", "with", "by", "at", "as",
    "and", "or", "not", "but", "if", "then", "else",
    "i", "you", "we", "they", "he", "she", "it", "our", "your", "their",
    "this", "that", "these", "those", "what", "who", "why", "how", "when", "where", "which",
    "any", "all", "some", "every", "no", "yes",
    "can", "could", "would", "should", "may", "might", "must", "will", "shall",
    "please", "tell", "me", "us", "show",
    # Platform/meta words that match nearly everything and add noise
    "information", "info", "data", "platform", "database", "system", "about",
    "regarding", "related", "anything", "something",
})


def _extract_search_terms(question: str, *, max_terms: int = 6) -> list[str]:
    """Pick meaningful search terms from a free-text question.

    Preference order:
      1. Capitalized multi-letter words (proper nouns — actor names, malware
         families, vendors). 'Lazarus' beats 'lazarus' beats nothing.
      2. Long lowercase words (>4 chars) not in the stop-list.
    Returns at most `max_terms` unique terms, lowercased.
    """
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", question)
    capitalized = [w for w in words if w[0].isupper() and w.lower() not in _STOPWORDS]
    other = [w for w in words if not w[0].isupper() and len(w) > 4 and w.lower() not in _STOPWORDS]

    seen: set[str] = set()
    out: list[str] = []
    for w in capitalized + other:
        wl = w.lower()
        if wl in seen:
            continue
        seen.add(wl)
        out.append(w)
        if len(out) >= max_terms:
            break
    return out


# Per-resource trimmers — keep token budgets sane. We never need the full row,
# just enough for the LLM to say "yes, we have N matches, here's a summary".
def _trim_actor(a: dict) -> dict:
    return {
        "id": str(a.get("id", "")),
        "name": a.get("name"),
        "aliases": (a.get("aliases") or [])[:5],
        "mitre_id": a.get("mitre_id"),
        "origin_country": a.get("origin_country"),
        "motivation": a.get("motivation"),
        "target_sectors": (a.get("target_sectors") or [])[:6],
        "target_countries": (a.get("target_countries") or [])[:6],
        "status": a.get("status"),
        "last_seen": a.get("last_seen"),
    }


def _trim_article(a: dict) -> dict:
    return {
        "id": str(a.get("id", "")),
        "title": a.get("title"),
        "url": a.get("url"),
        "source": a.get("source"),
        "published_at": a.get("published_at"),
        "summary": (a.get("summary") or "")[:300],
        "tags": (a.get("tags") or [])[:6],
    }


def _trim_threat(t: dict) -> dict:
    return {
        "id": str(t.get("id", "")),
        "type": t.get("type"),
        "title": t.get("title"),
        "severity": t.get("severity"),
        "source": t.get("source"),
        "observed_at": t.get("observed_at"),
        "summary": (t.get("summary") or "")[:300],
    }


def _trim_cve(c: dict) -> dict:
    return {
        "cve_id": c.get("cve_id"),
        "cvss_v3_score": c.get("cvss_v3_score"),
        "epss": c.get("epss"),
        "kev": c.get("kev"),
        "published_at": c.get("published_at"),
        "description": (c.get("description") or "")[:300],
    }


def _trim_ioc(i: dict) -> dict:
    return {
        "id": str(i.get("id", "")),
        "type": i.get("type"),
        "value": i.get("normalized_value") or i.get("value"),
        "confidence_score": i.get("confidence_score"),
        "tags": (i.get("tags") or [])[:5],
        "first_seen": i.get("first_seen"),
        "last_seen": i.get("last_seen"),
    }


_TRIMMERS = {
    "actors": _trim_actor,
    "articles": _trim_article,
    "threats": _trim_threat,
    "cves": _trim_cve,
    "iocs": _trim_ioc,
}


async def search_platform(question: str, settings: Settings, jwt: str) -> dict[str, list[dict]]:
    """Search all intelligence resources for terms extracted from `question`.

    Returns a per-kind dict capped at 5 results each. Powers the `/ask`
    endpoint so the LLM can answer "do we have info about Lazarus" with the
    actual rows in our database, not its training-data guesses.
    """
    terms = _extract_search_terms(question)
    if not terms:
        return {k: [] for k in _TRIMMERS}

    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}

    # Build (kind, coroutine, term) tuples. One per (term × endpoint).
    # Cap parallelism at 6 terms × 5 endpoints = 30 in-flight requests, which
    # the local docker network handles without breaking a sweat.
    async with httpx.AsyncClient(headers=headers, timeout=8) as c:
        plans: list[tuple[str, Any]] = []
        for term in terms:
            plans.append(("actors",   c.get(f"{settings.threat_actors_url}/actors",       params={"q": term, "limit": 5})))
            plans.append(("articles", c.get(f"{settings.news_collector_url}/articles",    params={"q": term, "limit": 5})))
            plans.append(("threats",  c.get(f"{settings.threat_intel_url}/threats",       params={"q": term, "limit": 5})))
            plans.append(("cves",     c.get(f"{settings.vuln_intel_url}/cves",            params={"q": term, "limit": 5})))
            plans.append(("iocs",     c.get(f"{settings.ioc_collector_url}/indicators",   params={"value": term, "limit": 5})))

        results = await asyncio.gather(*(p[1] for p in plans), return_exceptions=True)

    out: dict[str, list[dict]] = {k: [] for k in _TRIMMERS}
    seen: dict[str, set[str]] = {k: set() for k in _TRIMMERS}

    for (kind, _), r in zip(plans, results):
        if isinstance(r, Exception):
            continue
        if getattr(r, "status_code", 500) != 200:
            continue
        try:
            data = r.json()
        except Exception:
            continue
        items = data if isinstance(data, list) else data.get("items", [])
        trim = _TRIMMERS[kind]
        for item in items[:5]:
            iid = str(item.get("id") or item.get("cve_id") or item.get("normalized_value") or item.get("value", ""))
            if not iid or iid in seen[kind]:
                continue
            seen[kind].add(iid)
            out[kind].append(trim(item))

    # Cap per kind so a chatty endpoint doesn't drown the prompt.
    for k in out:
        out[k] = out[k][:10]
    return out


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
                r = await c.get(f"{self._settings.threat_actors_url}/actors", params={"limit": 20})
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, dict) and "items" in data:
                        return data["items"][:20]
                    if isinstance(data, list):
                        return data[:20]
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

    async def analyst_notes(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        """Fetch analyst notes for a resource from the owning service."""
        kind = item.get("kind", "")
        resource_id = item.get("id") or item.get("cve_id", "")
        if not resource_id:
            return []

        url_map = {
            "article": f"{self._settings.news_collector_url}/articles/{resource_id}/notes",
            "cve": f"{self._settings.vuln_intel_url}/cves/{resource_id}/notes",
            "threat": f"{self._settings.threat_intel_url}/threats/{resource_id}/notes",
            "actor": f"{self._settings.threat_actors_url}/actors/{resource_id}/notes",
            "ioc": f"{self._settings.ioc_collector_url}/indicators/{resource_id}/notes",
        }
        url = url_map.get(kind)
        if not url:
            return []

        try:
            async with httpx.AsyncClient(headers=self._headers(), timeout=10) as c:
                r = await c.get(url)
                if r.status_code == 200:
                    data = r.json()
                    # Handle both list and {items: [...]} shapes
                    notes = data.get("items", data) if isinstance(data, dict) else data
                    # Sort: pinned first, then by created_at desc; limit to 20
                    if isinstance(notes, list):
                        notes.sort(
                            key=lambda n: (not n.get("pinned", False), n.get("created_at", "")),
                        )
                        return notes[:20]
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
            r = await c.get(f"{settings.threat_actors_url}/actors", params={"limit": 100})
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and "items" in data:
                    return data["items"][:100]
                if isinstance(data, list):
                    return data[:100]
    except Exception:
        pass
    return []


async def fetch_ransomware_victims(settings: Settings, jwt: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=10) as c:
            r = await c.get(f"{settings.threat_actors_url}/ransomware/victims", params={"limit": 50})
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and "items" in data:
                    return data["items"][:50]
                if isinstance(data, list):
                    return data[:50]
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


async def fetch_trending_signals(
    settings: Settings,
    jwt: str,
    *,
    threat_days: int = 7,
    article_hours: int = 48,
    kev_days: int = 14,
    victim_days: int = 7,
) -> dict[str, list[dict]]:
    """Pull what's actively trending across the platform.

    These are the inputs that turn the daily brief from "generic exec summary"
    into "what's hot right now". Each window is a sensible default for a daily
    briefing — adjust via kwargs for a weekly digest or hourly poll later.

    Returns a dict the brief prompt can read directly. Keys are stable; missing
    services degrade to empty lists (the cycle still ships a brief).
    """
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    since_threats = (now - timedelta(days=threat_days)).isoformat()
    since_articles = (now - timedelta(hours=article_hours)).isoformat()
    since_kev = (now - timedelta(days=kev_days)).isoformat()
    since_victims = (now - timedelta(days=victim_days)).isoformat()

    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}

    async def _safe(coro):
        try:
            return await coro
        except Exception:
            return None

    async with httpx.AsyncClient(headers=headers, timeout=15) as c:
        # Parallel fan-out across all signal sources. Each request is wrapped
        # so a slow / dead source can't pull the whole brief down with it.
        recent_threats, recent_articles, recent_kev, recent_victims, recent_iocs = await asyncio.gather(
            _safe(c.get(f"{settings.threat_intel_url}/threats",
                        params={"since": since_threats, "limit": 30})),
            _safe(c.get(f"{settings.news_collector_url}/articles",
                        params={"since": since_articles, "limit": 20})),
            _safe(c.get(f"{settings.vuln_intel_url}/cves",
                        params={"kev": "true", "since": since_kev, "limit": 20})),
            _safe(c.get(f"{settings.threat_actors_url}/ransomware/victims",
                        params={"since": since_victims, "limit": 30})),
            _safe(c.get(f"{settings.ioc_collector_url}/indicators",
                        params={"since": (now - timedelta(hours=24)).isoformat(),
                                "min_confidence": "0.7", "limit": 25})),
        )

    def _items(resp) -> list[dict]:
        if resp is None or getattr(resp, "status_code", 500) != 200:
            return []
        try:
            data = resp.json()
        except Exception:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
        return []

    # Trim each row to essentials so the brief prompt stays comfortably under
    # GitHub Models' 8K-token request ceiling. Caps tuned empirically against
    # gpt-4o-mini after watching 413s; bump up if/when we switch to a larger
    # model (gpt-4o, claude, etc.) by overriding AI_PRIMARY_MODEL in secrets.
    trending_threats = [
        {
            "type": t.get("type"),
            "title": (t.get("title") or "")[:120],
            "severity": t.get("severity"),
            "observed_at": t.get("observed_at"),
            "summary": (t.get("summary") or "")[:140],
        }
        for t in _items(recent_threats)[:8]
    ]
    trending_articles = [
        {
            "title": (a.get("title") or "")[:120],
            "source": a.get("source_name") or a.get("source"),
            "published_at": a.get("published_at"),
            "tags": (a.get("tags") or [])[:4],
            "summary": (a.get("summary") or "")[:140],
        }
        for a in _items(recent_articles)[:8]
    ]
    trending_kev = [
        {
            "cve_id": c.get("cve_id"),
            "cvss_v3_score": c.get("cvss_v3_score"),
            "epss": c.get("epss"),
            "kev_date_added": c.get("kev_date_added"),
            "kev_ransomware_use": c.get("kev_ransomware_use"),
            "description": (c.get("description") or "")[:140],
        }
        for c in _items(recent_kev)[:8]
    ]
    trending_victims = [
        {
            "victim_name": v.get("victim_name"),
            "sector": v.get("sector"),
            "country": v.get("country"),
            "disclosed_at": v.get("disclosed_at"),
            "group_name": v.get("group_name"),
        }
        for v in _items(recent_victims)[:12]
    ]
    trending_iocs = [
        {
            "type": i.get("type"),
            "value": i.get("normalized_value") or i.get("value"),
            "tags": (i.get("tags") or [])[:3],
        }
        for i in _items(recent_iocs)[:10]
    ]

    return {
        "window_days_threats": threat_days,
        "window_hours_articles": article_hours,
        "window_days_kev": kev_days,
        "window_days_ransomware_victims": victim_days,
        "recent_threats": trending_threats,
        "recent_articles": trending_articles,
        "recent_kev_additions": trending_kev,
        "recent_ransomware_victims": trending_victims,
        "recent_high_confidence_iocs": trending_iocs,
    }


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
