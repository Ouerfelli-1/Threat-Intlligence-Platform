"""
Profile -> ASM auto-sync.

When the company profile is patched, diff old vs new identity fields
(public_domains, public_ip_ranges, asn_numbers) and push adds/removes
to the ASM service as targets under a dedicated scope.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx

log = logging.getLogger(__name__)

SYNC_SCOPE_NAME = "profile:auto-sync"


def _collect(identity: dict[str, Any] | None) -> set[tuple[str, str]]:
    """Extract (type, value) tuples from an identity block."""
    if not identity:
        return set()
    out: set[tuple[str, str]] = set()
    for d in identity.get("public_domains", []):
        out.add(("domain", d))
    for r in identity.get("public_ip_ranges", []):
        out.add(("cidr" if "/" in r else "ip", r))
    for a in identity.get("asn_numbers", []):
        out.add(("asn", a))
    return out


async def _ensure_scope(
    asm_url: str, headers: dict[str, str]
) -> uuid.UUID | None:
    """Find or create the auto-sync scope in ASM. Returns scope id or None on failure."""
    try:
        async with httpx.AsyncClient(headers=headers, timeout=15) as c:
            r = await c.get(f"{asm_url}/scopes")
            r.raise_for_status()
            for scope in r.json():
                if scope.get("name") == SYNC_SCOPE_NAME:
                    return uuid.UUID(scope["id"])
            # Create it
            r2 = await c.post(
                f"{asm_url}/scopes",
                json={"name": SYNC_SCOPE_NAME, "description": "Auto-synced from company profile"},
            )
            r2.raise_for_status()
            return uuid.UUID(r2.json()["id"])
    except Exception:
        log.exception("Failed to ensure ASM scope '%s'", SYNC_SCOPE_NAME)
        return None


async def _get_existing_targets(
    asm_url: str, headers: dict[str, str], scope_id: uuid.UUID
) -> dict[tuple[str, str], str]:
    """Get existing targets for the scope. Returns {(type, value): target_id}."""
    try:
        async with httpx.AsyncClient(headers=headers, timeout=15) as c:
            r = await c.get(f"{asm_url}/targets", params={"scope_id": str(scope_id)})
            r.raise_for_status()
            return {
                (t["type"], t["value"]): t["id"]
                for t in r.json()
            }
    except Exception:
        log.exception("Failed to get existing ASM targets")
        return {}


async def sync_to_asm(
    old_payload: dict[str, Any] | None,
    new_payload: dict[str, Any],
    asm_url: str,
    service_jwt: str,
) -> None:
    """Diff old/new profile identity and push target adds/removes to ASM."""
    old_identity = (old_payload or {}).get("identity")
    new_identity = new_payload.get("identity")

    old_items = _collect(old_identity)
    new_items = _collect(new_identity)

    added = new_items - old_items
    removed = old_items - new_items

    if not added and not removed:
        log.debug("Profile sync: no identity changes for ASM")
        return

    headers = {"Authorization": f"Bearer {service_jwt}"} if service_jwt else {}

    scope_id = await _ensure_scope(asm_url, headers)
    if scope_id is None:
        log.error("Cannot sync to ASM: scope creation failed")
        return

    existing = await _get_existing_targets(asm_url, headers, scope_id)

    async with httpx.AsyncClient(headers=headers, timeout=15) as c:
        for typ, val in added:
            if (typ, val) in existing:
                log.debug("Target (%s, %s) already exists in ASM, skipping", typ, val)
                continue
            try:
                r = await c.post(
                    f"{asm_url}/targets",
                    json={
                        "scope_id": str(scope_id),
                        "type": typ,
                        "value": val,
                        "description": "Auto-synced from company profile",
                    },
                )
                r.raise_for_status()
                log.info("ASM target added: %s %s", typ, val)
            except Exception:
                log.exception("Failed to add ASM target: %s %s", typ, val)

        for typ, val in removed:
            target_id = existing.get((typ, val))
            if target_id is None:
                log.debug("Target (%s, %s) not found in ASM for removal", typ, val)
                continue
            try:
                r = await c.delete(f"{asm_url}/targets/{target_id}")
                r.raise_for_status()
                log.info("ASM target removed: %s %s", typ, val)
            except Exception:
                log.exception("Failed to remove ASM target: %s %s", typ, val)

    log.info(
        "Profile -> ASM sync complete: %d added, %d removed",
        len(added), len(removed),
    )
