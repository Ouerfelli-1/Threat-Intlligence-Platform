"""Map MITRE ATT&CK TTPs from text."""
from __future__ import annotations
from typing import Any

from pydantic import BaseModel

from tip_ai import OpenRouterClient, generate_structured
from tip_common import get_logger

from app.prompts import PROMPT_VERSION
from app.settings import Settings

logger = get_logger("orchestrator.actions.map_ttps")

MAP_TTPS_PROMPT = """\
You are a MITRE ATT&CK expert.  Analyse the provided threat information and
map every identifiable technique/sub-technique to its ATT&CK ID.

For each mapping, return:
- technique_id: e.g. "T1566.001"
- technique_name: e.g. "Phishing: Spearphishing Attachment"
- confidence: float 0.0–1.0

Return ONLY valid JSON matching the schema.  If no TTPs are identifiable,
return an empty list.
"""


class MappedTTP(BaseModel):
    technique_id: str
    technique_name: str
    confidence: float = 0.5


class MapTTPsOutput(BaseModel):
    ttps: list[MappedTTP] = []


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
    if not text:
        return {"ttps": []}

    try:
        result = await generate_structured(
            ai,
            system_prompt=MAP_TTPS_PROMPT,
            user_payload={"text": text[:8000]},
            schema=MapTTPsOutput,
            prompt_version=PROMPT_VERSION,
        )
        return result.model_dump()
    except Exception as exc:
        logger.error("map_ttps_failed", error=str(exc))
        return {"error": str(exc)}
