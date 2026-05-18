"""Detection correlation action."""
from __future__ import annotations
from typing import Any

from tip_ai import OpenRouterClient, generate_structured
from tip_common import get_logger

from app.analysis import CorrelationOutput
from app.prompts import DETECTION_CORRELATION_PROMPT, PROMPT_VERSION
from app.settings import Settings

logger = get_logger("orchestrator.actions.correlation")


async def run(
    ai: OpenRouterClient,
    item: dict[str, Any],
    context: dict[str, Any],
    settings: Settings,
    jwt: str,
) -> dict[str, Any]:
    profile = context.get("company_profile", {})
    alerts = context.get("wazuh_alerts", [])
    actors = context.get("actors", [])

    try:
        result = await generate_structured(
            ai,
            system_prompt=DETECTION_CORRELATION_PROMPT,
            user_payload={
                "wazuh_alerts": alerts[:100],
                "known_actors": [
                    {"name": a.get("name"), "ttps": a.get("ttps", [])}
                    for a in actors[:20]
                ],
                "company_profile": profile,
            },
            schema=CorrelationOutput,
            prompt_version=PROMPT_VERSION,
        )
        return result.model_dump()
    except Exception as exc:
        logger.error("correlation_failed", error=str(exc))
        return {"error": str(exc)}
