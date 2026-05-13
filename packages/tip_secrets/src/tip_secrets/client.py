import asyncio
from typing import Any

import httpx

from tip_common.errors import UpstreamError
from tip_common.logging_setup import get_logger
from tip_http import build_resilient_client

logger = get_logger("tip_secrets")


class SecretNotFound(Exception):
    pass


class SecretsClient:
    """Client for the secrets service. Caches values in memory."""

    def __init__(
        self,
        *,
        base_url: str,
        service_name: str,
        bootstrap_token: str,
        service_jwt: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_name = service_name
        self._bootstrap_token = bootstrap_token
        self._service_jwt = service_jwt
        self._cache: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._http = build_resilient_client(base_url=self._base_url)

    def set_service_jwt(self, jwt: str) -> None:
        self._service_jwt = jwt

    async def close(self) -> None:
        await self._http.close()

    async def get(self, name: str, *, default: str | None = None, required: bool = True) -> str:
        if name in self._cache:
            return self._cache[name]
        async with self._lock:
            if name in self._cache:
                return self._cache[name]
            value = await self._fetch(name)
            if value is None:
                if required:
                    raise SecretNotFound(name)
                if default is not None:
                    self._cache[name] = default
                    return default
                raise SecretNotFound(name)
            self._cache[name] = value
            return value

    async def get_optional(self, name: str) -> str | None:
        try:
            return await self.get(name, required=False)
        except SecretNotFound:
            return None

    async def _fetch(self, name: str) -> str | None:
        if self._service_jwt:
            try:
                return await self._fetch_with_jwt(name)
            except UpstreamError:
                return await self._fetch_via_bootstrap(name)
        return await self._fetch_via_bootstrap(name)

    async def _fetch_with_jwt(self, name: str) -> str | None:
        headers = {"Authorization": f"Bearer {self._service_jwt}"}
        try:
            resp = await self._http.client.get(f"/secrets/{name}", headers=headers)
        except httpx.HTTPError as e:
            raise UpstreamError(f"secrets fetch failed: {e}") from e
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise UpstreamError(f"secrets returned {resp.status_code}: {resp.text}")
        data: dict[str, Any] = resp.json()
        return data.get("value")

    async def _fetch_via_bootstrap(self, name: str) -> str | None:
        payload = {
            "service_name": self._service_name,
            "bootstrap_token": self._bootstrap_token,
            "secret_name": name,
        }
        try:
            resp = await self._http.client.post("/internal/bootstrap-fetch", json=payload)
        except httpx.HTTPError as e:
            raise UpstreamError(f"secrets bootstrap fetch failed: {e}") from e
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise UpstreamError(f"secrets bootstrap returned {resp.status_code}: {resp.text}")
        data: dict[str, Any] = resp.json()
        return data.get("value")
