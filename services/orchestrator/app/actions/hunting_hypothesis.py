"""Generate threat-hunting hypotheses from context."""
from __future__ import annotations
from typing import Any

from pydantic import BaseModel

from tip_ai import OpenRouterClient, generate_structured
from tip_common import get_logger

from app.prompts import PROMPT_VERSION
from app.settings import Settings

logger = get_logger("orchestrator.actions.hunting_hypothesis")

HUNTING_PROMPT = """\
You are a senior threat hunter.  Given the threat information, generate a
concrete threat-hunting hypothesis that a SOC team can execute.

Return:
- hypothesis: one-paragraph plain-English hypothesis
- splunk_query: a Splunk SPL query that tests the hypothesis (best effort)
- wazuh_rule: a Wazuh detection rule snippet (XML) that operationalises it

Return ONLY valid JSON matching the schema.
"""


class HuntingHypothesisOutput(BaseModel):
    hypothesis: str
    splunk_query: str = ""
    wazuh_rule: str = ""


async def run(
    ai: OpenRouterClient,
    item: dict[str, Any],
    context: dict[str, Any],
    settings: Settings,
    jwt: str,
) -> dict[str, Any]:
    text = (
        item.get("content_text")
        or item.get("summary")
        or item.get("description")
        or item.get("title")
        or ""
    )
    profile = context.get("company_profile", {})

    try:
        result = await generate_structured(
            ai,
            system_prompt=HUNTING_PROMPT,
            user_payload={"threat_info": text[:6000], "company_profile": profile},
            schema=HuntingHypothesisOutput,
            prompt_version=PROMPT_VERSION,
        )
        return result.model_dump()
    except Exception as exc:
        logger.error("hunting_hypothesis_failed", error=str(exc))
        return {"error": str(exc)}
