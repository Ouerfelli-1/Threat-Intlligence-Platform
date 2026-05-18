"""Executive brief synthesis action."""
from __future__ import annotations
from typing import Any

from tip_ai import OpenRouterClient, generate_structured
from tip_common import get_logger

from app.analysis import BriefOutput
from app.prompts import BRIEF_SYNTHESIS_PROMPT, PROMPT_VERSION
from app.settings import Settings

logger = get_logger("orchestrator.actions.brief")


async def run(
    ai: OpenRouterClient,
    item: dict[str, Any],
    context: dict[str, Any],
    settings: Settings,
    jwt: str,
) -> dict[str, Any]:
    profile = context.get("company_profile", {})

    try:
        result = await generate_structured(
            ai,
            system_prompt=BRIEF_SYNTHESIS_PROMPT,
            user_payload={
                "company_profile": profile,
                "cve_relevance": context.get("cve_relevance", {}),
                "actor_likelihood": context.get("actor_likelihood", {}),
                "correlations": context.get("correlations", {}),
            },
            schema=BriefOutput,
            prompt_version=PROMPT_VERSION,
        )
        return result.model_dump()
    except Exception as exc:
        logger.error("brief_failed", error=str(exc))
        return {"error": str(exc)}
