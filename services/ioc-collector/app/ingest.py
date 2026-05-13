import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tip_common.logging_setup import get_logger
from tip_schemas import (
    SOURCE_RELIABILITY,
    ConfidenceInputs,
    DataType,
    IndicatorType,
    compute_confidence,
    normalize_indicator,
)
from tip_source_health import SourceHealthRepository

from app.models import Indicator, IndicatorSource

logger = get_logger("ioc.ingest")


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        # Some sources (e.g. MalwareBazaar) return naive timestamps. Force UTC.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


async def _recompute_confidence(session: AsyncSession, indicator: Indicator) -> None:
    corroboration = (
        await session.execute(
            select(func.count()).select_from(IndicatorSource).where(
                IndicatorSource.indicator_id == indicator.id
            )
        )
    ).scalar_one()
    source_names = (
        (await session.execute(
            select(IndicatorSource.source_name).where(IndicatorSource.indicator_id == indicator.id)
        )).scalars().all()
    )
    reliability = max(
        [SOURCE_RELIABILITY.get(s, 0.6) for s in source_names] or [0.6]
    )
    days_since = max(0.0, (datetime.now(timezone.utc) - indicator.first_seen).total_seconds() / 86400.0)
    inputs = ConfidenceInputs(
        source_reliability=reliability,
        corroboration_count=int(corroboration),
        days_since_seen=days_since,
        extraction_quality=1.0,
    )
    indicator.confidence_score = compute_confidence(DataType.IOC, inputs)
    indicator.confidence_inputs = inputs.model_dump()


async def upsert_indicator_from_source(
    session: AsyncSession,
    source_name: str,
    record: dict,
) -> tuple[bool, bool]:
    """Returns (created_indicator, created_source_row)."""
    try:
        normalized = normalize_indicator(record["type"], record["raw_value"])
    except (ValueError, KeyError):
        return False, False

    existing = await session.scalar(
        select(Indicator).where(
            Indicator.type == record["type"],
            Indicator.normalized_value == normalized,
        )
    )
    now = datetime.now(timezone.utc)
    first_seen = _parse_dt(record.get("first_seen"))
    last_seen = _parse_dt(record.get("last_seen"))

    created_indicator = False
    if existing is None:
        indicator = Indicator(
            type=record["type"],
            normalized_value=normalized,
            raw_value=record["raw_value"],
            first_seen=first_seen,
            last_seen=last_seen,
            tags=list(filter(None, record.get("tags") or [])),
        )
        session.add(indicator)
        await session.flush()
        created_indicator = True
    else:
        indicator = existing
        if last_seen > indicator.last_seen:
            indicator.last_seen = last_seen
        merged = set(indicator.tags or []) | set(filter(None, record.get("tags") or []))
        indicator.tags = sorted(merged)

    stmt = (
        insert(IndicatorSource)
        .values(
            indicator_id=indicator.id,
            source_name=source_name,
            source_id=record.get("source_id"),
            first_reported_at=first_seen,
            last_reported_at=last_seen,
            malware_family=record.get("malware_family"),
            threat_type=record.get("threat_type"),
            raw=record.get("raw") or {},
        )
        .on_conflict_do_update(
            index_elements=["indicator_id", "source_name"],
            set_={
                "last_reported_at": last_seen,
                "malware_family": record.get("malware_family"),
                "threat_type": record.get("threat_type"),
                "raw": record.get("raw") or {},
            },
        )
        .returning(IndicatorSource.indicator_id)
    )
    await session.execute(stmt)
    await _recompute_confidence(session, indicator)
    return created_indicator, True


async def ingest_records(
    session_factory,
    *,
    source_name: str,
    records: list[dict],
) -> tuple[int, int]:
    created = 0
    updated = 0
    async with session_factory() as session:
        for record in records:
            try:
                ci, _ = await upsert_indicator_from_source(session, source_name, record)
                if ci:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                logger.warning(
                    "ioc_ingest_record_failed",
                    source=source_name,
                    error=str(e),
                    type=record.get("type"),
                )
        await session.commit()
    return created, updated


async def run_ingestion_cycle(
    *,
    session_factory,
    health: SourceHealthRepository,
    threatfox_fn,
    malbazaar_fn,
    otx_fn,
) -> dict:
    """Run all configured sources in parallel. Each is isolated."""
    run_id = uuid.uuid4().hex
    sources = [
        ("threatfox", threatfox_fn),
        ("malwarebazaar", malbazaar_fn),
        ("otx", otx_fn),
    ]
    active = [(name, fn) for name, fn in sources if fn is not None]

    async def _run(name: str, fn) -> tuple[str, list[dict] | None, str | None]:
        try:
            records = await fn()
            return name, records, None
        except Exception as e:
            return name, None, str(e)

    results = await asyncio.gather(*(_run(n, f) for n, f in active), return_exceptions=False)

    added = 0
    updated = 0
    failed: list[str] = []
    succeeded = 0
    for name, records, err in results:
        if err is not None or records is None:
            failed.append(name)
            continue
        c, u = await ingest_records(session_factory, source_name=name, records=records)
        added += c
        updated += u
        succeeded += 1

    return {
        "run_id": run_id,
        "status": "success",
        "sources_attempted": len(active),
        "sources_succeeded": succeeded,
        "indicators_added": added,
        "indicators_updated": updated,
        "failed_sources": failed,
    }
