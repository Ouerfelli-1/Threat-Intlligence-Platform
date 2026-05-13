"""
Core domain monitoring pipeline.
Ported from AvailableServices/Domain Watcher/scripts/checkdomain.py.
Sync DNS calls run in a thread pool executor so they don't block the event loop.
"""
import asyncio
import hashlib
import json
import logging
import re
import secrets
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

log = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)


def _run_sync(fn, *args):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(_executor, partial(fn, *args))


# ---------------------------------------------------------------------------
# DNS helpers (sync — run via executor)
# ---------------------------------------------------------------------------

def _query_record(name: str, rtype: str) -> list[str]:
    import dns.resolver
    try:
        answers = dns.resolver.resolve(name, rtype, lifetime=5)
        return [r.to_text() for r in answers]
    except Exception:
        return []


def _normalize(records: list[str]) -> list[str]:
    return sorted({r.strip().rstrip(".").lower() for r in records if r})


def _get_domain_data(domain: str) -> dict:
    import dns.resolver
    a = _normalize(_query_record(domain, "A"))
    aaaa = _normalize(_query_record(domain, "AAAA"))
    mx_raw = _query_record(domain, "MX")
    ns = _normalize(_query_record(domain, "NS"))

    mx_records = []
    for mx in mx_raw:
        parts = mx.split(maxsplit=1)
        if len(parts) == 2:
            priority, host = parts
            mx_records.append({"priority": int(priority), "host": host.rstrip(".").lower()})

    return {
        "domain": domain,
        "a_records": a,
        "aaaa_records": aaaa,
        "mx_records": sorted(mx_records, key=lambda x: x.get("priority", 0)),
        "ns_records": ns,
    }


def _fetch_and_hash(domain: str) -> tuple[str, str]:
    """Returns (content_text, sha256_hash). Empty strings on failure."""
    import requests
    from bs4 import BeautifulSoup, Comment

    for scheme in ("https", "http"):
        try:
            resp = requests.get(
                f"{scheme}://{domain}",
                timeout=15,
                allow_redirects=True,
                headers={"User-Agent": "TIP-DomainWatch/1.0"},
                stream=True,
            )
            resp.raise_for_status()
            chunks, total = [], 0
            for chunk in resp.iter_content(chunk_size=65536, decode_unicode=True):
                total += len(chunk)
                if total > 5 * 1024 * 1024:
                    resp.close()
                    return "", ""
                chunks.append(chunk)
            html = "".join(chunks)
            break
        except Exception:
            continue
    else:
        return "", ""

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()
    text = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True)).strip()
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return text, content_hash


# ---------------------------------------------------------------------------
# Async pipeline
# ---------------------------------------------------------------------------

async def check_domain(domain: str, screenshot_dir: str) -> dict[str, Any]:
    """Run all monitoring checks for one domain and return a details dict."""
    domain_data = await _run_sync(_get_domain_data, domain)
    content_text, content_hash = await _run_sync(_fetch_and_hash, domain)
    screenshot_path = await _take_screenshot(domain, screenshot_dir)

    return {
        "dns": domain_data,
        "content_hash": content_hash,
        "screenshot_path": screenshot_path,
    }


async def _take_screenshot(domain: str, screenshot_dir: str) -> str | None:
    """Capture a Playwright screenshot and return the file path, or None on failure."""
    import os
    import uuid as _uuid
    from datetime import datetime, timezone

    try:
        from playwright.async_api import async_playwright

        os.makedirs(screenshot_dir, exist_ok=True)
        filename = f"{domain}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{_uuid.uuid4().hex[:8]}.png"
        path = os.path.join(screenshot_dir, filename)

        async with async_playwright() as p:
            browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
            page = await browser.new_page()
            try:
                await page.goto(f"https://{domain}", timeout=20000, wait_until="domcontentloaded")
                await page.screenshot(path=path, full_page=False)
            except Exception:
                # Try http fallback
                try:
                    await page.goto(f"http://{domain}", timeout=20000, wait_until="domcontentloaded")
                    await page.screenshot(path=path, full_page=False)
                except Exception:
                    path = None
            finally:
                await browser.close()

        return path
    except Exception as exc:
        log.warning("screenshot domain=%s error=%s", domain, exc)
        return None


def diff_dns(before: dict, after: dict) -> list[dict]:
    """Return list of detected changes between two domain detail dicts."""
    changes = []
    for field in ("a_records", "aaaa_records", "ns_records"):
        b = set(before.get("dns", {}).get(field, []))
        a = set(after.get("dns", {}).get(field, []))
        if b != a:
            changes.append({
                "type": f"dns_{field}_changed",
                "before": sorted(b),
                "after": sorted(a),
            })

    if before.get("content_hash") and after.get("content_hash"):
        if before["content_hash"] != after["content_hash"]:
            changes.append({
                "type": "content_hash_changed",
                "before": {"hash": before["content_hash"]},
                "after": {"hash": after["content_hash"]},
            })

    return changes
