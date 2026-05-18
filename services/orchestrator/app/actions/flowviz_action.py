"""Flowviz attack-flow generation action."""
from __future__ import annotations
from typing import Any

from tip_common import get_logger

from app.context import generate_flow_for_finding
from app.settings import Settings

logger = get_logger("orchestrator.actions.flowviz")


async def run(
    ai,  # unused — flowviz has its own AI client
    item: dict[str, Any],
    context: dict[str, Any],
    settings: "Settings",
    jwt: str,
) -> dict[str, Any]:
    """Generate an attack flow for the item's description/summary."""
    description = (
        item.get("description")
        or item.get("summary")
        or item.get("title")
        or str(item)
    )
    try:
        flow = await generate_flow_for_finding(description, settings, jwt)
        return {"attack_flow": flow}
    except Exception as exc:
        logger.error("flowviz_failed", error=str(exc))
        return {"error": str(exc)}
