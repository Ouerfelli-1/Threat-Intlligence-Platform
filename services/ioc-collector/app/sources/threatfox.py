from datetime import datetime, timezone
from typing import Any

from tip_common.logging_setup import get_logger
from tip_http import build_resilient_client, fetch_with_resilience
from tip_schemas import IndicatorType
from tip_source_health import SourceHealthRepository

logger = get_logger("ioc.threatfox")


_TF_TYPE_MAP = {
    "ip:port": IndicatorType.IP,
    "ip": IndicatorType.IP,
    "domain": IndicatorType.DOMAIN,
    "url": IndicatorType.URL,
    "md5_hash": IndicatorType.MD5,
    "sha1_hash": IndicatorType.SHA1,
    "sha256_hash": IndicatorType.SHA256,
}


def _strip_port(value: str) -> str:
    return value.split(":", 1)[0] if ":" in value and value.count(":") == 1 else value


def _normalize_row(row: dict[str, Any]) -> dict[str, Any] | None:
    raw_type = row.get("ioc_type")
    ind_type = _TF_TYPE_MAP.get(raw_type or "")
    if ind_type is None:
        return None
    raw_value = (row.get("ioc") or "").strip()
    if not raw_value:
        return None
    if raw_type == "ip:port":
        raw_value = _strip_port(raw_value)
    return {
        "type": ind_type.value,
        "raw_value": raw_value,
        "first_seen": row.get("first_seen"),
        "last_seen": row.get("last_seen"),
        "source_id": str(row.get("id")) if row.get("id") else None,
        "malware_family": row.get("malware_printable"),
        "threat_type": row.get("threat_type"),
        "tags": [row.get("malware")] if row.get("malware") else [],
        "raw": row,
    }


async def fetch_recent_iocs(
    *,
    api_key: str,
    days: int = 3,
    base_url: str,
    health: SourceHealthRepository,
) -> list[dict[str, Any]]:
    """Pull recent IOCs from ThreatFox."""

    async def _call() -> dict[str, Any]:
        async with build_resilient_client() as client:
            resp = await client.client.post(
                base_url,
                json={"query": "get_iocs", "days": days},
                headers={"Auth-Key": api_key},
            )
            resp.raise_for_status()
            return resp.json()

    result = await fetch_with_resilience("threatfox", _call, health=health)
    if not result.success or result.value is None:
        return []
    data = result.value.get("data") or []
    out = []
    for row in data:
        normalized = _normalize_row(row)
        if normalized is not None:
            out.append(normalized)
    return out
