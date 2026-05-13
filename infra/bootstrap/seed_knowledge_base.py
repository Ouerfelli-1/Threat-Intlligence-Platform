"""First-boot knowledge-base seed.

Runs once after all services are healthy. Triggers a full sync of every
ingestion source so the platform never serves an empty database. On every
subsequent boot it sees the BOOTSTRAP_SEED_COMPLETED marker in the secrets
vault and exits cleanly.

Sequence:
  1. Auth /login → admin JWT (using env-provided admin credentials)
  2. CMDB PATCH /profile  (seeds Banque Maghreb Atlantique profile if absent)
  3. threat-actors POST /refresh/full   (MITRE + ransomware FULL history)
  4. ioc-collector POST /ingest/run
  5. vuln-intel POST /refresh/kev, /refresh/epss, /refresh/nvd
  6. news-collector POST /ingest/run
  7. threat-intel POST /ingest/run
  8. Mark BOOTSTRAP_SEED_COMPLETED=<timestamp> in secrets

Idempotent: re-running is safe; each service's upsert/ON CONFLICT path handles repeats.

Env vars used:
  AUTH_URL                  (default http://auth:8000)
  SECRETS_URL               (default http://secrets:8012)
  SECRETS_BOOTSTRAP_TOKEN   (shared bootstrap token)
  CMDB_URL, THREAT_ACTORS_URL, IOC_COLLECTOR_URL, VULN_INTEL_URL,
  NEWS_COLLECTOR_URL, THREAT_INTEL_URL
  BOOTSTRAP_ADMIN_USERNAME, BOOTSTRAP_ADMIN_PASSWORD
  SEED_PROFILE_PATH         (default /seed/companyprofile.json)
  FORCE_SEED                (set to "1" to ignore the marker and re-seed)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

MARKER_NAME = "BOOTSTRAP_SEED_COMPLETED"


def _env(name: str, default: str | None = None) -> str:
    val = os.environ.get(name, default)
    if val is None:
        raise RuntimeError(f"{name} env var is required")
    return val


SECRETS_URL = _env("SECRETS_URL", "http://secrets:8012")
AUTH_URL = _env("AUTH_URL", "http://auth:8000")
CMDB_URL = _env("CMDB_URL", "http://cmdb:8007")
THREAT_ACTORS_URL = _env("THREAT_ACTORS_URL", "http://threat-actors:8005")
IOC_COLLECTOR_URL = _env("IOC_COLLECTOR_URL", "http://ioc-collector:8004")
VULN_INTEL_URL = _env("VULN_INTEL_URL", "http://vuln-intel:8002")
NEWS_COLLECTOR_URL = _env("NEWS_COLLECTOR_URL", "http://news-collector:8001")
THREAT_INTEL_URL = _env("THREAT_INTEL_URL", "http://threat-intel:8003")
BOOTSTRAP_TOKEN = _env("SECRETS_BOOTSTRAP_TOKEN")
ADMIN_USER = _env("BOOTSTRAP_ADMIN_USERNAME", "admin")
ADMIN_PASS = _env("BOOTSTRAP_ADMIN_PASSWORD", "changeme")
SEED_PROFILE_PATH = _env("SEED_PROFILE_PATH", "/seed/companyprofile.json")
FORCE_SEED = os.environ.get("FORCE_SEED", "").lower() in ("1", "true", "yes")


async def _check_marker(client: httpx.AsyncClient) -> str | None:
    """Returns the timestamp of a previous seed if present, None otherwise."""
    if FORCE_SEED:
        print(f"[seed] FORCE_SEED set — ignoring previous marker")
        return None
    try:
        r = await client.post(
            f"{SECRETS_URL}/internal/bootstrap-fetch",
            json={
                "service_name": "seed",
                "bootstrap_token": BOOTSTRAP_TOKEN,
                "secret_name": MARKER_NAME,
            },
        )
        if r.status_code == 200:
            return (r.json() or {}).get("value")
    except Exception as e:
        print(f"[seed] could not check marker: {e}")
    return None


async def _login(client: httpx.AsyncClient) -> str:
    print(f"[seed] login as {ADMIN_USER}")
    r = await client.post(
        f"{AUTH_URL}/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


async def _seed_profile(client: httpx.AsyncClient, token: str) -> None:
    path = Path(SEED_PROFILE_PATH)
    if not path.exists():
        print(f"[seed] {path} not found; skipping CMDB profile")
        return
    # Skip if profile already exists
    r = await client.get(
        f"{CMDB_URL}/profile/latest",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if r.status_code == 200:
        print("[seed] company profile already present; skipping")
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    r = await client.patch(
        f"{CMDB_URL}/profile",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    print(f"[seed] company profile seeded (version={r.json().get('version')})")


async def _trigger(
    client: httpx.AsyncClient,
    token: str,
    url: str,
    path: str,
    label: str,
    *,
    accept_status: tuple[int, ...] = (200, 202),
) -> None:
    print(f"[seed] triggering {label} → POST {url}{path}")
    try:
        r = await client.post(
            f"{url}{path}",
            json={},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if r.status_code in accept_status:
            print(f"[seed]   ok ({r.status_code})")
        else:
            print(f"[seed]   WARNING http={r.status_code} body={r.text[:200]}")
    except Exception as e:
        print(f"[seed]   ERROR {type(e).__name__}: {e}")


async def _write_marker(client: httpx.AsyncClient, token: str) -> None:
    """Write the marker via secrets POST /secrets (needs admin JWT)."""
    payload = {
        "name": MARKER_NAME,
        "value": datetime.now(timezone.utc).isoformat(),
        "metadata": {"set_by": "bootstrap-seed"},
    }
    r = await client.post(
        f"{SECRETS_URL}/secrets",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if r.status_code < 400:
        print(f"[seed] marker {MARKER_NAME} written")
    else:
        print(f"[seed] failed to write marker http={r.status_code} body={r.text[:200]}")


async def main() -> int:
    async with httpx.AsyncClient() as client:
        existing = await _check_marker(client)
        if existing:
            print(f"[seed] marker present (seeded at {existing}); nothing to do")
            return 0

        # Bring everything up
        token = await _login(client)
        await _seed_profile(client, token)

        # Heavy data pulls. Each service triggers a background job; we fire them
        # in parallel and let the schedulers drive subsequent refreshes.
        await asyncio.gather(
            _trigger(client, token, THREAT_ACTORS_URL, "/refresh/full", "actors+ransomware (FULL)"),
            _trigger(client, token, IOC_COLLECTOR_URL, "/ingest/run", "iocs"),
            _trigger(client, token, VULN_INTEL_URL, "/refresh/kev", "cve KEV"),
            _trigger(client, token, VULN_INTEL_URL, "/refresh/epss", "cve EPSS"),
            _trigger(client, token, VULN_INTEL_URL, "/refresh/nvd", "cve NVD"),
            _trigger(client, token, NEWS_COLLECTOR_URL, "/ingest/run", "news"),
            _trigger(client, token, THREAT_INTEL_URL, "/ingest/run", "threats"),
            return_exceptions=True,
        )

        # Mark complete — the heavy pulls run in background, but firing them is
        # all this script is responsible for. Tracking completion is the job
        # of source_health + scheduler.
        await _write_marker(client, token)
        print("[seed] knowledge-base seed complete")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
