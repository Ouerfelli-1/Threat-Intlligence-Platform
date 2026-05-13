import csv
import gzip
import io
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tip_http import build_resilient_client, fetch_with_resilience
from tip_source_health import SourceHealthRepository

from app.models import EPSS


async def _download_csv_gz(url: str) -> bytes:
    async with build_resilient_client() as client:
        resp = await client.client.get(url)
        resp.raise_for_status()
        return resp.content


async def sync_epss(
    *,
    session: AsyncSession,
    url: str,
    health: SourceHealthRepository,
) -> tuple[int, int, int]:
    result = await fetch_with_resilience("epss", lambda: _download_csv_gz(url), health=health)
    if not result.success or result.value is None:
        return 0, 0, 0

    raw = gzip.decompress(result.value).decode("utf-8")
    lines = raw.splitlines()
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    reader = csv.DictReader(lines)
    now = datetime.now(timezone.utc)
    seen = added = 0
    for row in reader:
        cve_id = (row.get("cve") or "").strip()
        if not cve_id:
            continue
        try:
            score = float(row["epss"])
            pct = float(row["percentile"])
        except (KeyError, ValueError):
            continue
        seen += 1
        stmt = (
            insert(EPSS)
            .values(cve_id=cve_id, epss=score, percentile=pct, scored_at=now)
            .on_conflict_do_update(
                index_elements=["cve_id"],
                set_={"epss": score, "percentile": pct, "scored_at": now},
            )
        )
        await session.execute(stmt)
        added += 1
    await session.commit()
    return seen, added, 0
