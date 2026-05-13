from typing import Any

from tip_http import build_resilient_client, fetch_with_resilience
from tip_schemas import IndicatorType
from tip_source_health import SourceHealthRepository


async def fetch_recent_samples(
    *,
    api_key: str,
    base_url: str,
    health: SourceHealthRepository,
    limit: int = 100,
) -> list[dict[str, Any]]:
    async def _call() -> dict[str, Any]:
        async with build_resilient_client() as client:
            resp = await client.client.post(
                base_url,
                data={"query": "get_recent", "selector": "time"},
                headers={"Auth-Key": api_key},
            )
            resp.raise_for_status()
            return resp.json()

    result = await fetch_with_resilience("malwarebazaar", _call, health=health)
    if not result.success or result.value is None:
        return []
    items = (result.value.get("data") or [])[:limit]
    out: list[dict[str, Any]] = []
    for it in items:
        sha256 = it.get("sha256_hash")
        if not sha256:
            continue
        out.append({
            "type": IndicatorType.SHA256.value,
            "raw_value": sha256,
            "first_seen": it.get("first_seen"),
            "last_seen": it.get("last_seen"),
            "source_id": sha256,
            "malware_family": it.get("signature"),
            "threat_type": it.get("file_type"),
            "tags": list(filter(None, [it.get("signature"), it.get("file_type")])),
            "raw": it,
        })
    return out
