"""HTTP client for the LiteLLM proxy.

The platform runs LiteLLM as a standalone proxy service (`litellm:4000`) that
exposes an OpenAI-compatible REST API in front of every upstream provider.
Apps that need AI just POST OpenAI-format chat-completions bodies to it; the
proxy handles routing, authentication to the actual upstream, retries, and
fallbacks.

This file is the in-process client that talks to that proxy. It exposes the
same `.chat() / .model / extract_content() / extract_json() / .close()`
interface as OpenRouterClient so `synthesis.py` works with either.

Why a proxy instead of the LiteLLM SDK in-process:
  * Centralized routing — the proxy holds the API keys, not every service.
  * Centralized retry/fallback logic, configured once in /etc/litellm/config.yaml.
  * GitHub Models (and a few other providers) only work reliably through the
    proxy because the SDK path mis-routes certain model ids.
  * Rotating an API key only requires restarting the proxy, not 5 services.

Resilience:
  * The proxy is configured with `router_settings.fallbacks` so a primary
    provider failure automatically retries through OpenRouter on the proxy
    side — the client doesn't need to know.
  * Network failure to the proxy itself surfaces as `LiteLLMError`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from tip_common.logging_setup import get_logger

logger = get_logger("tip_ai.litellm")


class LiteLLMError(Exception):
    """Generic failure talking to the LiteLLM proxy or upstream provider."""
    pass


class LiteLLMRateLimitError(LiteLLMError):
    """The proxy returned 429 (rate limit exceeded on the upstream provider).

    Distinguishable from LiteLLMError so callers can degrade gracefully:
    return 429 to clients, skip an analysis step rather than abort the cycle,
    surface a "try again later" message in the UI, etc. `retry_after_seconds`
    carries the upstream's suggested wait (parsed best-effort from the error
    body; None if the provider didn't say).
    """
    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class LiteLLMRequestTooLargeError(LiteLLMError):
    """The proxy returned 413 — input + max_tokens exceeded the model ceiling.

    A bug-and-retry case for us: callers should trim payload, not blame the
    user. Separate from LiteLLMError so observability can split prompt-too-big
    from genuine upstream failures.
    """
    pass


@dataclass
class LiteLLMMessage:
    role: str
    content: str


class LiteLLMClient:
    """OpenAI-format HTTP client pointed at the LiteLLM proxy.

    Args:
        proxy_url:        base URL of the proxy, e.g. "http://litellm:4000"
        master_key:       Bearer token configured on the proxy (LITELLM_MASTER_KEY)
        primary_model:    default model id forwarded to the proxy
        fallback_models:  client-side fallback chain (the proxy ALSO has its own;
                          these are belt-and-braces, not strictly required)
        timeout_seconds:  per-call timeout
        extra_headers:    additional headers sent on every request (rare)
    """
    def __init__(
        self,
        *,
        proxy_url: str,
        master_key: str,
        primary_model: str,
        fallback_models: list[str] | None = None,
        timeout_seconds: float = 120.0,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self._proxy_url = proxy_url.rstrip("/")
        self._primary_model = primary_model
        self._fallback_models = list(fallback_models or [])
        self._master_key = master_key or ""
        headers = {"Content-Type": "application/json"}
        # Only set Authorization when we actually have a key. Sending an empty
        # header confuses some HTTP/2 stacks and produces a misleading "401 with
        # no body" rather than a clean diagnosable error.
        if master_key:
            headers["Authorization"] = f"Bearer {master_key}"
        if extra_headers:
            headers.update(extra_headers)
        self._client = httpx.AsyncClient(
            base_url=self._proxy_url,
            headers=headers,
            timeout=httpx.Timeout(timeout_seconds),
        )

    @property
    def model(self) -> str:
        """Display name — written to insight rows as `model_name`."""
        return self._primary_model

    @property
    def primary_model(self) -> str:
        return self._primary_model

    @property
    def fallback_models(self) -> list[str]:
        return list(self._fallback_models)

    @property
    def provider_keys(self) -> dict[str, str]:
        # Proxy mode: keys live on the proxy, not here. Kept for back-compat
        # with introspection used by /admin tools.
        return {}

    async def close(self) -> None:
        await self._client.aclose()

    async def chat(
        self,
        messages: list[LiteLLMMessage] | list,
        *,
        response_format_json: bool = True,
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._primary_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}
        if self._fallback_models:
            # The LiteLLM proxy honours a per-request `fallbacks` field as
            # client-side backup on top of the server-side fallback config.
            payload["fallbacks"] = self._fallback_models

        try:
            resp = await self._client.post("/v1/chat/completions", json=payload)
        except httpx.HTTPError as e:
            raise LiteLLMError(f"litellm proxy unreachable: {e}") from e

        if resp.status_code >= 400:
            # The proxy returns OpenAI-style error envelopes; surface verbatim
            # so admins can see if it was an upstream auth issue, missing key,
            # model-not-found, etc. Split out 429 + 413 because callers should
            # handle them differently from generic 500s.
            body = resp.text[:600]
            msg = f"litellm proxy returned {resp.status_code}: {body}"
            if resp.status_code == 429:
                # Best-effort parse of "Please wait N seconds before retrying"
                retry_after: int | None = None
                import re as _re
                m = _re.search(r"wait\s+(\d+)\s+seconds", body, _re.IGNORECASE)
                if m:
                    try:
                        retry_after = int(m.group(1))
                    except ValueError:
                        retry_after = None
                # Also honor the standard Retry-After header if present
                ra_hdr = resp.headers.get("retry-after")
                if ra_hdr and retry_after is None:
                    try:
                        retry_after = int(ra_hdr)
                    except ValueError:
                        retry_after = None
                raise LiteLLMRateLimitError(msg, retry_after_seconds=retry_after)
            if resp.status_code == 413:
                raise LiteLLMRequestTooLargeError(msg)
            raise LiteLLMError(msg)

        data = resp.json()
        usage = data.get("usage") or {}
        actual = data.get("model") or self._primary_model
        logger.info(
            "litellm_call",
            requested=self._primary_model,
            actual=actual,
            fellback=(actual != self._primary_model),
            tokens_in=usage.get("prompt_tokens"),
            tokens_out=usage.get("completion_tokens"),
        )
        return data

    # ---- response-shape helpers (match OpenRouterClient) -----------------------

    @staticmethod
    def extract_content(response: dict[str, Any]) -> str:
        choices = response.get("choices") or []
        if not choices:
            raise LiteLLMError("no choices in litellm proxy response")
        message = choices[0].get("message") or {}
        return message.get("content") or ""

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        s = text.strip()
        if s.startswith("```"):
            first_nl = s.find("\n")
            if first_nl != -1:
                s = s[first_nl + 1 :]
            if s.endswith("```"):
                s = s[:-3]
            elif "```" in s:
                s = s[: s.rfind("```")]
        return s.strip()

    @staticmethod
    def extract_json(response: dict[str, Any]) -> dict[str, Any]:
        content = LiteLLMClient.extract_content(response)
        cleaned = LiteLLMClient._strip_code_fences(content)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise LiteLLMError(f"invalid JSON content: {e}; raw={content[:300]}") from e
