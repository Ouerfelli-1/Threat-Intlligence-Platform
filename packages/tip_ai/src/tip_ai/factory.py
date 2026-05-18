"""Construct an AI client from secret-bag config.

Centralizes the "which provider to use" decision so every consuming service
shares one rule and one set of env-var conventions.

Decision tree:
  1. If `ai_provider=openrouter` (legacy override), use the in-process
     OpenRouterClient — talks directly to openrouter.ai with no proxy.
  2. Otherwise (default), build a LiteLLMClient that POSTs to the standalone
     LiteLLM proxy at `settings.litellm_proxy_url`. The proxy holds the actual
     upstream API keys (GitHub PAT, OpenAI, Anthropic, etc.) and handles
     routing + fallbacks server-side.

The proxy mode is preferred because:
  * Provider API keys live in one place (the proxy container env, populated
    from the secrets vault at proxy startup) instead of being copied into
    every consuming service.
  * Rotating a key only requires restarting the proxy.
  * Some providers (notably GitHub Models) are flaky through the LiteLLM
    Python SDK but reliable through the proxy's REST surface.
"""
from __future__ import annotations

from typing import Any

from tip_ai.litellm_client import LiteLLMClient
from tip_ai.openrouter import OpenRouterClient
from tip_common.logging_setup import get_logger

logger = get_logger("tip_ai.factory")


def build_ai_client(secrets: dict[str, str], settings: Any) -> Any:
    """Return a LiteLLMClient (default, proxy mode) or OpenRouterClient (legacy).

    Args:
        secrets:  the bag of secrets pulled from the secrets service. Must
                  contain `LITELLM_MASTER_KEY` for proxy mode (the value the
                  proxy validates in incoming Authorization headers). For the
                  legacy openrouter path, `OPENROUTER_API_KEY` is required.
        settings: the service's Settings object. Inspected for:
                    ai_provider           — "litellm" | "openrouter"
                    ai_primary_model      — primary model id (e.g. "github/gpt-4o-mini")
                    ai_fallback_models    — comma-separated list (optional)
                    ai_openrouter_model   — legacy override for OpenRouter client
                    litellm_proxy_url     — base URL of the proxy
    """
    provider = (getattr(settings, "ai_provider", "litellm") or "litellm").lower()

    if provider == "openrouter":
        # Legacy path — straight to OpenRouter, no proxy in the loop.
        model = getattr(settings, "ai_openrouter_model", None) or "anthropic/claude-3-5-haiku"
        api_key = secrets.get("OPENROUTER_API_KEY", "")
        if not api_key:
            logger.warning("openrouter_client_no_key — calls will return 401")
        return OpenRouterClient(api_key=api_key, model=model)

    # --- Proxy mode (default) -------------------------------------------------
    primary = getattr(settings, "ai_primary_model", None) or "anthropic/claude-3-5-haiku-20241022"
    fallbacks_raw = getattr(settings, "ai_fallback_models", "") or ""
    fallbacks = [m.strip() for m in fallbacks_raw.split(",") if m.strip()]
    if not fallbacks:
        # Sensible default fallback chain — picks models that ACTUALLY exist on
        # OpenRouter so we don't 400 on the fallback path. The proxy ALSO has
        # its own server-side fallback config; these are belt-and-braces.
        if primary.startswith("github/"):
            # GitHub Models hosts the OpenAI catalog; OpenRouter's equivalent
            # is openai/<same-model-name> (case-sensitive).
            model_name = primary.split("/", 1)[1].lower()
            fallbacks = [f"openrouter/openai/{model_name}", "openrouter/anthropic/claude-3-5-haiku"]
        elif primary.startswith("openrouter/"):
            fallbacks = ["openrouter/anthropic/claude-3-5-haiku"]
        else:
            # Direct provider (openai/, anthropic/, etc.) — route through
            # OpenRouter as fallback with the same model id.
            fallbacks = [f"openrouter/{primary}", "openrouter/anthropic/claude-3-5-haiku"]

    proxy_url = getattr(settings, "litellm_proxy_url", None) or "http://litellm:4000"
    master_key = secrets.get("LITELLM_MASTER_KEY", "")
    if not master_key:
        # Don't crash; just warn loudly. The proxy will return 401 on the first
        # request, which surfaces cleanly in logs as LiteLLMError(401).
        logger.warning(
            "litellm_client_no_master_key — calls will return 401 from the proxy. "
            "Did seed_secrets.py run? Is LITELLM_MASTER_KEY in the secrets vault?"
        )

    return LiteLLMClient(
        proxy_url=proxy_url,
        master_key=master_key,
        primary_model=primary,
        fallback_models=fallbacks,
    )
