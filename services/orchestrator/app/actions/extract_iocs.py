"""Extract IOCs from text using AI.

Results are written to the insight payload's ``iocs_extracted`` key — NOT
promoted to ``ioc.indicators``.  Promotion is a separate analyst action.
"""
from __future__ import annotations
from typing import Any

from pydantic import BaseModel

from tip_ai import OpenRouterClient, generate_structured
from tip_common import get_logger

from app.prompts import PROMPT_VERSION
from app.settings import Settings

logger = get_logger("orchestrator.actions.extract_iocs")

EXTRACT_IOCS_PROMPT = """\
You are an expert Cyber Threat Intelligence analyst.  Extract all Indicators of
Compromise (IOCs) from the provided text.

For each IOC, return:
- type: ip | domain | url | hash_md5 | hash_sha1 | hash_sha256 | email
- value: the raw string
- context: one sentence explaining where in the text it appeared

Return ONLY valid JSON matching the schema.  If no IOCs are found, return an
empty list.
"""


class ExtractedIOC(BaseModel):
    type: str
    value: str
    context: str = ""


class ExtractIOCsOutput(BaseModel):
    iocs_extracted: list[ExtractedIOC] = []


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
        return {"iocs_extracted": []}

    try:
        result = await generate_structured(
            ai,
            system_prompt=EXTRACT_IOCS_PROMPT,
            user_payload={"text": text[:8000]},
            schema=ExtractIOCsOutput,
            prompt_version=PROMPT_VERSION,
        )
        return result.model_dump()
    except Exception as exc:
        logger.error("extract_iocs_failed", error=str(exc))
        return {"error": str(exc)}
