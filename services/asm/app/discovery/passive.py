"""
Passive subdomain/host discovery.
Ported from AvailableServices/ASM/engine/modules/subdomain_enum.py — passive methods only.
Active brute-force (active_enum, brute_with_ffuf, _check_subdomain) are intentionally omitted.
"""
import asyncio
import logging
import re
from urllib.parse import urlparse

import httpx

from tip_http import build_resilient_client

log = logging.getLogger(__name__)


def _clean(domain: str) -> str:
    return domain.strip().lower().rstrip(".")


def _is_valid_subdomain(candidate: str, root: str) -> bool:
    candidate = _clean(candidate)
    root = _clean(root)
    return candidate.endswith(f".{root}") or candidate == root


async def _crtsh(domain: str, client: httpx.AsyncClient) -> set[str]:
    try:
        resp = await client.get(f"https://crt.sh/?q=%.{domain}&output=json", timeout=30)
        resp.raise_for_status()
        results = set()
        for entry in resp.json():
            for name in entry.get("name_value", "").split("\n"):
                cleaned = _clean(name.replace("*", ""))
                if cleaned and _is_valid_subdomain(cleaned, domain):
                    results.add(cleaned)
        return results
    except Exception as exc:
        log.debug("crtsh error=%s", exc)
        return set()


async def _hackertarget(domain: str, client: httpx.AsyncClient) -> set[str]:
    try:
        resp = await client.get(f"https://api.hackertarget.com/hostsearch/?q={domain}", timeout=15)
        resp.raise_for_status()
        results = set()
        for line in resp.text.split("\n"):
            if "," in line:
                cleaned = _clean(line.split(",")[0])
                if cleaned and _is_valid_subdomain(cleaned, domain):
                    results.add(cleaned)
        return results
    except Exception as exc:
        log.debug("hackertarget error=%s", exc)
        return set()


async def _wayback(domain: str, client: httpx.AsyncClient) -> set[str]:
    url = f"http://web.archive.org/cdx/search/cdx?url=*.{domain}/*&output=json&fl=original&collapse=urlkey&limit=500"
    try:
        resp = await client.get(url, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        results = set()
        for item in data[1:]:
            if item:
                parsed = urlparse(item[0] if item[0].startswith("http") else f"http://{item[0]}")
                cleaned = _clean(parsed.netloc)
                if cleaned and _is_valid_subdomain(cleaned, domain):
                    results.add(cleaned)
        return results
    except Exception as exc:
        log.debug("wayback error=%s", exc)
        return set()


async def _anubisdb(domain: str, client: httpx.AsyncClient) -> set[str]:
    try:
        resp = await client.get(f"https://jldc.me/anubis/subdomains/{domain}", timeout=20)
        resp.raise_for_status()
        results = set()
        for sub in resp.json():
            cleaned = _clean(sub)
            if cleaned and _is_valid_subdomain(cleaned, domain):
                results.add(cleaned)
        return results
    except Exception as exc:
        log.debug("anubisdb error=%s", exc)
        return set()


async def _urlscan(domain: str, client: httpx.AsyncClient) -> set[str]:
    try:
        resp = await client.get(
            f"https://urlscan.io/api/v1/search/?q=domain:{domain}",
            headers={"User-Agent": "TIP-Platform/1.0"},
            timeout=15,
        )
        resp.raise_for_status()
        results = set()
        for result in resp.json().get("results", []):
            for key in ("page", "task"):
                d = _clean(result.get(key, {}).get("domain", ""))
                if d and _is_valid_subdomain(d, domain):
                    results.add(d)
        return results
    except Exception as exc:
        log.debug("urlscan error=%s", exc)
        return set()


async def passive_subdomain_enum(domain: str) -> set[str]:
    """Run all passive sources concurrently and return discovered subdomains."""
    async with build_resilient_client() as client:
        results = await asyncio.gather(
            _crtsh(domain, client),
            _hackertarget(domain, client),
            _wayback(domain, client),
            _anubisdb(domain, client),
            _urlscan(domain, client),
            return_exceptions=True,
        )
    combined: set[str] = set()
    for r in results:
        if isinstance(r, set):
            combined.update(r)
    return combined


async def shodan_host_lookup(ip: str, api_key: str) -> dict:
    """Fetch Shodan host info; returns empty dict if key absent or request fails."""
    if not api_key:
        return {}
    try:
        async with build_resilient_client(base_url="https://api.shodan.io") as client:
            resp = await client.get(f"/shodan/host/{ip}", params={"key": api_key}, timeout=15)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        log.debug("shodan error=%s", exc)
        return {}
