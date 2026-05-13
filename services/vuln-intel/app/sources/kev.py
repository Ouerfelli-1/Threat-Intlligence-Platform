from datetime import date

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tip_http import build_resilient_client, fetch_with_resilience
from tip_source_health import SourceHealthRepository

from app.models import KEV


async def _download_json(url: str) -> dict:
    async with build_resilient_client() as client:
        resp = await client.client.get(url)
        resp.raise_for_status()
        return resp.json()


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


async def sync_kev(
    *,
    session: AsyncSession,
    url: str,
    health: SourceHealthRepository,
) -> tuple[int, int, int]:
    result = await fetch_with_resilience("cisa-kev", lambda: _download_json(url), health=health)
    if not result.success or result.value is None:
        return 0, 0, 0

    vulnerabilities = result.value.get("vulnerabilities") or []
    seen = added = 0
    for v in vulnerabilities:
        cve_id = v.get("cveID")
        if not cve_id:
            continue
        payload = {
            "cve_id": cve_id,
            "vendor": v.get("vendorProject"),
            "product": v.get("product"),
            "name": v.get("vulnerabilityName"),
            "date_added": _parse_date(v.get("dateAdded")),
            "due_date": _parse_date(v.get("dueDate")),
            "ransomware_use": (v.get("knownRansomwareCampaignUse") or "Unknown").lower() == "known",
            "notes": v.get("notes"),
        }
        seen += 1
        stmt = (
            insert(KEV)
            .values(**payload)
            .on_conflict_do_update(
                index_elements=["cve_id"],
                set_={k: payload[k] for k in payload if k != "cve_id"},
            )
        )
        await session.execute(stmt)
        added += 1
    await session.commit()
    return seen, added, 0
