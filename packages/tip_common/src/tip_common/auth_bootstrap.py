"""Helpers each non-auth service calls at startup to wire production JWT auth.

Two functions, both no-ops when `settings.disable_auth` is True:

- fetch_auth_public_key(settings): pulls AUTH_RS256_PUBLIC_KEY from the secrets
  service via the bootstrap endpoint. Stored on `app.state.auth_public_key` so
  JWTAuthMiddleware can resolve it lazily.

- obtain_service_jwt(settings, service_name): fetches the service's own
  SVC_<NAME>_BOOTSTRAP_TOKEN from secrets, then POSTs auth/service-login to
  exchange it for a 24h service JWT. Stored on `app.state.service_jwt`.
"""
from __future__ import annotations

import httpx

from tip_common.logging_setup import get_logger
from tip_common.settings import BaseServiceSettings

logger = get_logger("tip_common.auth_bootstrap")


def _svc_token_key(service_name: str) -> str:
    return f"SVC_{service_name.upper().replace('-', '_')}_BOOTSTRAP_TOKEN"


async def _bootstrap_fetch(
    client: httpx.AsyncClient,
    settings: BaseServiceSettings,
    service_name: str,
    secret_name: str,
) -> str | None:
    resp = await client.post(
        f"{settings.secrets_url}/internal/bootstrap-fetch",
        json={
            "service_name": service_name,
            "bootstrap_token": settings.secrets_bootstrap_token,
            "secret_name": secret_name,
        },
    )
    if resp.status_code != 200:
        logger.warning(
            "bootstrap_fetch_failed",
            service=service_name,
            secret=secret_name,
            status=resp.status_code,
        )
        return None
    return resp.json().get("value")


async def fetch_auth_public_key(
    settings: BaseServiceSettings,
    service_name: str,
) -> str | None:
    """Fetch AUTH_RS256_PUBLIC_KEY from secrets. Returns None if unreachable or missing."""
    if settings.disable_auth:
        return None
    if not settings.secrets_bootstrap_token:
        logger.warning("auth_bootstrap_skipped_no_token", service=service_name)
        return None
    async with httpx.AsyncClient(timeout=30.0) as client:
        return await _bootstrap_fetch(
            client, settings, service_name, "AUTH_RS256_PUBLIC_KEY"
        )


async def obtain_service_jwt(
    settings: BaseServiceSettings,
    service_name: str,
) -> str | None:
    """Exchange this service's bootstrap token for a 24h service JWT.

    Returns None when DISABLE_AUTH or any step fails — caller treats it as best-effort.
    """
    if settings.disable_auth:
        return None
    if not settings.secrets_bootstrap_token:
        logger.warning("service_jwt_skipped_no_token", service=service_name)
        return None
    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await _bootstrap_fetch(
            client, settings, service_name, _svc_token_key(service_name)
        )
        if not token:
            logger.warning("service_jwt_no_bootstrap_token", service=service_name)
            return None
        resp = await client.post(
            f"{settings.auth_url}/service-login",
            json={"service_name": service_name, "bootstrap_token": token},
        )
        if resp.status_code != 200:
            logger.warning(
                "service_login_failed",
                service=service_name,
                status=resp.status_code,
                body=resp.text[:200],
            )
            return None
        return resp.json().get("access_token")


async def wire_auth(app, settings: BaseServiceSettings, service_name: str) -> None:
    """Convenience: call from each service's `_startup` hook."""
    public_key = await fetch_auth_public_key(settings, service_name)
    if public_key:
        app.state.auth_public_key = public_key
    jwt = await obtain_service_jwt(settings, service_name)
    if jwt:
        app.state.service_jwt = jwt
