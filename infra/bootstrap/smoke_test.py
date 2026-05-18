"""End-to-end smoke test: hit /health on every service.

Usage:
    python infra/bootstrap/smoke_test.py

Returns non-zero if any service is unreachable.
"""

import asyncio
import sys

import httpx

SERVICES = {
    "auth": 8000,
    "news-collector": 8001,
    "vuln-intel": 8002,
    "threat-intel": 8003,
    "ioc-collector": 8004,
    "threat-actors": 8005,
    "integrations": 8006,
    "cmdb": 8007,
    "flowviz": 8008,
    "asm": 8009,
    "domainwatch": 8010,
    "scheduler": 8011,
    "secrets": 8012,
    "indicator-intel": 8013,
    "orchestrator": 8014,
}

# LiteLLM proxy uses a non-standard health path (/health/liveliness). Probed
# separately so a "[BAD] litellm" row makes operators check the proxy first
# before chasing AI failures in downstream services.
LITELLM_HEALTH_URL = "http://localhost:4000/health/liveliness"


async def _probe(client: httpx.AsyncClient, name: str, port: int) -> tuple[str, bool, str]:
    try:
        resp = await client.get(f"http://localhost:{port}/health", timeout=5.0)
        if resp.status_code == 200:
            return name, True, "ok"
        return name, False, f"http {resp.status_code}"
    except Exception as e:
        return name, False, f"{type(e).__name__}: {e}"


async def _probe_litellm(client: httpx.AsyncClient) -> tuple[str, bool, str]:
    try:
        resp = await client.get(LITELLM_HEALTH_URL, timeout=5.0)
        if resp.status_code == 200:
            return "litellm", True, "ok"
        return "litellm", False, f"http {resp.status_code}"
    except Exception as e:
        return "litellm", False, f"{type(e).__name__}: {e}"


async def _main() -> int:
    async with httpx.AsyncClient() as client:
        tasks = [_probe(client, n, p) for n, p in SERVICES.items()]
        tasks.append(_probe_litellm(client))
        results = await asyncio.gather(*tasks)
    rc = 0
    for name, ok, detail in results:
        marker = "OK " if ok else "BAD"
        print(f"[{marker}] {name:18s} {detail}")
        if not ok:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
