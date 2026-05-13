import json
from dataclasses import dataclass
from typing import Any

import httpx

from tip_common.logging_setup import get_logger
from tip_http import build_resilient_client

logger = get_logger("tip_ai.openrouter")


class OpenRouterError(Exception):
    pass


@dataclass
class OpenRouterMessage:
    role: str
    content: str


class OpenRouterClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 90.0,
        referer: str = "https://tip.local",
        app_title: str = "TIP Platform",
    ) -> None:
        self._model = model
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": referer,
                "X-Title": app_title,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout_seconds),
        )

    @property
    def model(self) -> str:
        return self._model

    async def close(self) -> None:
        await self._client.aclose()

    async def chat(
        self,
        messages: list[OpenRouterMessage],
        *,
        response_format_json: bool = True,
        temperature: float = 0.2,
        max_tokens: int = 1536,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}
        try:
            resp = await self._client.post("/chat/completions", json=payload)
        except httpx.HTTPError as e:
            raise OpenRouterError(f"openrouter request failed: {e}") from e
        if resp.status_code >= 400:
            raise OpenRouterError(f"openrouter returned {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        usage = data.get("usage", {})
        logger.info(
            "openrouter_call",
            model=self._model,
            tokens_in=usage.get("prompt_tokens"),
            tokens_out=usage.get("completion_tokens"),
        )
        return data

    @staticmethod
    def extract_content(response: dict[str, Any]) -> str:
        choices = response.get("choices") or []
        if not choices:
            raise OpenRouterError("no choices in openrouter response")
        message = choices[0].get("message") or {}
        return message.get("content") or ""

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Strip ```json … ``` or ``` … ``` wrappers some models emit despite JSON mode."""
        s = text.strip()
        if s.startswith("```"):
            # remove the opening fence (with optional language tag) and the closing fence
            first_nl = s.find("\n")
            if first_nl != -1:
                s = s[first_nl + 1 :]
            if s.endswith("```"):
                s = s[: -3]
            elif "```" in s:
                # closing fence followed by trailing prose — keep only up to it
                s = s[: s.rfind("```")]
        return s.strip()

    @staticmethod
    def extract_json(response: dict[str, Any]) -> dict[str, Any]:
        content = OpenRouterClient.extract_content(response)
        cleaned = OpenRouterClient._strip_code_fences(content)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise OpenRouterError(f"invalid JSON content: {e}; raw={content[:300]}") from e
