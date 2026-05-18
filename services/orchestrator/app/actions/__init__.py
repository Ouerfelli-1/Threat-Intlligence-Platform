"""Action module registry.

Each action is an async callable with signature:
    async def action(ai, item, context, settings, jwt) -> dict
"""
from __future__ import annotations

from typing import Any, Callable, Coroutine

from tip_ai import OpenRouterClient
from app.settings import Settings

ActionFn = Callable[
    [OpenRouterClient, dict[str, Any], dict[str, Any], Settings, str],
    Coroutine[Any, Any, dict[str, Any]],
]

# Lazy imports to keep the registry light
def _get_registry() -> dict[str, ActionFn]:
    from app.actions.cve_relevance import run as cve_relevance
    from app.actions.actor_likelihood import run as actor_likelihood
    from app.actions.correlation import run as correlation
    from app.actions.brief import run as brief
    from app.actions.flowviz_action import run as flowviz
    from app.actions.extract_iocs import run as extract_iocs
    from app.actions.map_ttps import run as map_ttps
    from app.actions.hunting_hypothesis import run as hunting_hypothesis
    from app.actions.check_kev_exploited import run as check_kev_exploited

    return {
        "cve_relevance": cve_relevance,
        "actor_likelihood": actor_likelihood,
        "correlation": correlation,
        "brief": brief,
        "flowviz": flowviz,
        "extract_iocs": extract_iocs,
        "map_ttps": map_ttps,
        "hunting_hypothesis": hunting_hypothesis,
        "check_kev_exploited": check_kev_exploited,
    }


ACTIONS: dict[str, ActionFn] = {}


def get_actions() -> dict[str, ActionFn]:
    global ACTIONS
    if not ACTIONS:
        ACTIONS = _get_registry()
    return ACTIONS
