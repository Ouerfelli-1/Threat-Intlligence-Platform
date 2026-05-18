"""End-to-end diagnostic for the LiteLLM proxy chain.

Run when "AI chat doesn't work" — it pinpoints which link in the chain is
broken so you don't have to read four sets of logs to find out.

Usage:
    # From the host (Postgres on localhost, services on localhost ports):
    python infra/bootstrap/check_litellm.py

    # From inside a container (e.g. orchestrator):
    docker compose exec orchestrator python /app/infra/bootstrap/check_litellm.py

What it checks (in order — stops at the first failure):
    1. .env loaded? FERNET_KEY + SECRETS_BOOTSTRAP_TOKEN present?
    2. Secrets service reachable on http://localhost:8012 (or $SECRETS_URL)?
    3. Does the secrets vault contain LITELLM_MASTER_KEY?
       -> If not: seed_secrets.py wasn't re-run after the LiteLLM swap.
    4. LiteLLM proxy reachable on http://localhost:4000 (or $LITELLM_PROXY_URL)?
       -> If not: `docker compose up -d litellm` not done, or build failed.
    5. Does the proxy accept the vault's master key?
       -> If 401: the proxy started before the vault had the key, so it
                 generated an ephemeral one. Restart the proxy.
    6. Does a real chat request succeed with the configured primary model?
       -> If 4xx: model id wrong, or upstream provider key missing in vault.
       -> If 5xx: upstream provider returned an error; fallback chain exhausted.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
SERVICE_NAME = "diagnostic"          # any string; secrets accepts the shared bootstrap token


def _load_env() -> None:
    """Populate os.environ from .env without pulling in python-dotenv."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)


def _fail(msg: str, hint: str = "") -> None:
    print(f"\n[FAIL] {msg}")
    if hint:
        print(f"       -> {hint}")
    sys.exit(1)


def _ok(msg: str) -> None:
    print(f"[OK]   {msg}")


def main() -> int:
    _load_env()

    bootstrap_token = os.environ.get("SECRETS_BOOTSTRAP_TOKEN", "")
    if not bootstrap_token:
        _fail(
            "SECRETS_BOOTSTRAP_TOKEN is empty",
            "Fill it in .env (generate: python -c 'import secrets; print(secrets.token_urlsafe(32))')",
        )
    _ok("SECRETS_BOOTSTRAP_TOKEN present in .env")

    secrets_url = os.environ.get("SECRETS_URL", "http://localhost:8012")
    litellm_url = os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000")
    print(f"       secrets_url  = {secrets_url}")
    print(f"       litellm_url  = {litellm_url}")

    with httpx.Client(timeout=10.0) as client:
        # 1. Secrets reachable
        try:
            r = client.get(f"{secrets_url}/health")
            r.raise_for_status()
        except Exception as e:
            _fail(
                f"Cannot reach secrets at {secrets_url}: {e}",
                "Is the secrets container up? `docker compose ps secrets`",
            )
        _ok(f"Secrets service responsive ({secrets_url}/health)")

        # 2. LITELLM_MASTER_KEY in vault?
        try:
            r = client.post(
                f"{secrets_url}/internal/bootstrap-fetch",
                json={
                    "service_name": SERVICE_NAME,
                    "bootstrap_token": bootstrap_token,
                    "secret_name": "LITELLM_MASTER_KEY",
                },
            )
        except Exception as e:
            _fail(f"bootstrap-fetch call failed: {e}", "Secrets reachable above — check its logs.")

        if r.status_code != 200:
            _fail(
                f"bootstrap-fetch returned {r.status_code}: {r.text[:200]}",
                "If 401: SECRETS_BOOTSTRAP_TOKEN in .env doesn't match what secrets was seeded with.",
            )

        master_key = (r.json() or {}).get("value", "")
        if not master_key:
            _fail(
                "Secrets vault has no value for LITELLM_MASTER_KEY",
                "Re-run: python infra/bootstrap/seed_secrets.py — then restart litellm.",
            )
        _ok(f"Vault has LITELLM_MASTER_KEY (length={len(master_key)})")

        # 3. Proxy reachable?
        try:
            r = client.get(f"{litellm_url}/health/liveliness")
        except Exception as e:
            _fail(
                f"Cannot reach LiteLLM proxy at {litellm_url}: {e}",
                "Is it up? `docker compose ps litellm` / `docker compose up -d litellm`",
            )
        if r.status_code != 200:
            _fail(f"Proxy liveliness returned {r.status_code}: {r.text[:200]}")
        _ok("LiteLLM proxy is alive")

        # 4. Vault's master key actually matches what the proxy expects?
        try:
            r = client.get(
                f"{litellm_url}/health",
                headers={"Authorization": f"Bearer {master_key}"},
            )
        except Exception as e:
            _fail(f"Proxy /health request failed: {e}")
        if r.status_code == 401:
            _fail(
                "Proxy rejected the vault's LITELLM_MASTER_KEY (401)",
                "The proxy started before the vault had the key, so it minted an ephemeral one. "
                "Restart the proxy to pick up the real key: `docker compose restart litellm`.",
            )
        if r.status_code >= 400:
            _fail(f"Proxy /health returned {r.status_code}: {r.text[:200]}")
        _ok("Proxy accepts the vault's master key")

        # 5. Real chat call?
        primary = os.environ.get("AI_PRIMARY_MODEL", "anthropic/claude-3-5-haiku-20241022")
        print(f"       trying primary model = {primary}")
        try:
            r = client.post(
                f"{litellm_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {master_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": primary,
                    "messages": [
                        {"role": "user", "content": "Reply with the single word: OK"},
                    ],
                    "max_tokens": 8,
                    "temperature": 0,
                },
                timeout=60.0,
            )
        except Exception as e:
            _fail(f"chat request transport error: {e}")

        if r.status_code >= 400:
            _fail(
                f"chat request returned {r.status_code}: {r.text[:500]}",
                "If 401 from upstream: provider key (OPENAI_API_KEY / ANTHROPIC_API_KEY / GITHUB_API_KEY / etc.) "
                "is missing in the vault. Add via Settings UI or credentials.env, then "
                "`docker compose restart litellm` so the proxy reloads it.",
            )

        data = r.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        actual = data.get("model", primary)
        fellback = actual != primary
        print(f"       reply       = {content!r}")
        print(f"       actual_model = {actual}{'  (fell back)' if fellback else ''}")
        _ok("End-to-end chat works through the LiteLLM proxy [done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
