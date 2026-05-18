"""CVE relevance scoring action."""
from __future__ import annotations
from typing import Any

from tip_ai import OpenRouterClient, generate_structured
from tip_common import get_logger

from app.analysis import CVERelevanceOutput
from app.prompts import CVE_RELEVANCE_PROMPT, PROMPT_VERSION
from app.settings import Settings

logger = get_logger("orchestrator.actions.cve_relevance")


async def run(
    ai: OpenRouterClient,
    item: dict[str, Any],
    context: dict[str, Any],
    settings: Settings,
    jwt: str,
) -> dict[str, Any]:
    """Score CVE relevance against the company profile."""
    profile = context.get("company_profile", {})
    cves = context.get("cves", [item] if item.get("cve_id") else [])

    try:
        result = await generate_structured(
            ai,
            system_prompt=CVE_RELEVANCE_PROMPT,
            user_payload={"cves": cves[:50], "company_profile": profile},
            schema=CVERelevanceOutput,
            prompt_version=PROMPT_VERSION,
        )
        return result.model_dump()
    except Exception as exc:
        logger.error("cve_relevance_failed", error=str(exc))
        return {"error": str(exc)}
