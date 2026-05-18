"""AI policy resolver.

Precedence: scope=resource > scope=category > scope=global.
Within the same scope, higher ``priority`` wins.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models import AIPolicy

ALL_ACTIONS: list[str] = [
    "cve_relevance",
    "actor_likelihood",
    "correlation",
    "brief",
    "flowviz",
    "extract_iocs",
    "map_ttps",
    "hunting_hypothesis",
    "check_kev_exploited",
]


@dataclass
class PolicyDecision:
    """Resolved effective policy for a single item."""

    mode: str = "on_demand"  # full_auto | category_auto | on_demand
    actions: list[str] = field(default_factory=list)
    cmdb_filter: bool = False
    policy_id: str | None = None
    scope: str = "default"


def _category_for(item: dict[str, Any], resource_type: str) -> str | None:
    """Extract the category key from an item for policy matching."""
    if resource_type == "article":
        tags = item.get("tags") or []
        return tags[0] if tags else None
    if resource_type == "threat":
        return item.get("type")
    if resource_type == "cve":
        severity = item.get("severity") or item.get("cvss_v3_score")
        if severity is not None:
            try:
                s = float(severity)
                if s >= 9.0:
                    return "critical"
                if s >= 7.0:
                    return "high"
                if s >= 4.0:
                    return "medium"
                return "low"
            except (ValueError, TypeError):
                return str(severity).lower()
        return None
    if resource_type == "ioc":
        return item.get("type")
    if resource_type == "actor":
        motivations = item.get("motivation") or []
        return motivations[0] if motivations else None
    return None


def resolve_policy(
    item: dict[str, Any],
    resource_type: str,
    policies: list[AIPolicy],
) -> PolicyDecision:
    """Two-pass resolution: resource-specific → category → global.

    Parameters
    ----------
    item : dict
        The resource being evaluated (must include an ``id`` key).
    resource_type : str
        One of ``article``, ``cve``, ``threat``, ``actor``, ``ioc``.
    policies : list[AIPolicy]
        All **active** policies, pre-sorted or unsorted (we sort internally).
    """
    active = [p for p in policies if p.active]
    # Sort by priority DESC within each scope level
    active.sort(key=lambda p: p.priority, reverse=True)

    resource_id = str(item.get("id") or item.get("cve_id") or "")
    category = _category_for(item, resource_type)

    # Pass 1 — resource-specific
    for p in active:
        if (
            p.scope == "resource"
            and p.resource_type == resource_type
            and p.resource_id == resource_id
        ):
            return PolicyDecision(
                mode=p.mode,
                actions=list(p.actions or []),
                cmdb_filter=p.cmdb_filter,
                policy_id=str(p.id),
                scope="resource",
            )

    # Pass 2 — category
    if category:
        for p in active:
            if (
                p.scope == "category"
                and p.resource_type == resource_type
                and p.category == category
            ):
                return PolicyDecision(
                    mode=p.mode,
                    actions=list(p.actions or []),
                    cmdb_filter=p.cmdb_filter,
                    policy_id=str(p.id),
                    scope="category",
                )

    # Pass 3 — global
    for p in active:
        if p.scope == "global":
            return PolicyDecision(
                mode=p.mode,
                actions=list(p.actions or []),
                cmdb_filter=p.cmdb_filter,
                policy_id=str(p.id),
                scope="global",
            )

    # Fallback — on_demand, no auto processing
    return PolicyDecision()
