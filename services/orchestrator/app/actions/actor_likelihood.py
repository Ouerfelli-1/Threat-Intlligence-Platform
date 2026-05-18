"""Actor likelihood scoring action."""
from __future__ import annotations
from typing import Any

from tip_ai import OpenRouterClient, generate_structured
from tip_common import get_logger

from app.analysis import ActorLikelihoodOutput
from app.prompts import ACTOR_LIKELIHOOD_PROMPT, PROMPT_VERSION
from app.settings import Settings

logger = get_logger("orchestrator.actions.actor_likelihood")


async def run(
    ai: OpenRouterClient,
    item: dict[str, Any],
    context: dict[str, Any],
    settings: Settings,
    jwt: str,
) -> dict[str, Any]:
    profile = context.get("company_profile", {})
    actors = context.get("actors", [])
    victims = context.get("recent_victims", [])

    try:
        result = await generate_structured(
            ai,
            system_prompt=ACTOR_LIKELIHOOD_PROMPT,
            user_payload={
                "actors": actors[:50],
                "recent_victims": victims[:20],
                "company_profile": profile,
            },
            schema=ActorLikelihoodOutput,
            prompt_version=PROMPT_VERSION,
        )
        return result.model_dump()
    except Exception as exc:
        logger.error("actor_likelihood_failed", error=str(exc))
        return {"error": str(exc)}
