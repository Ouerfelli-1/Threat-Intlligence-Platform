from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import Table, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tip_cache import Cache
from tip_common.logging_setup import get_logger

logger = get_logger("tip_source_health")

ACTIVE = "active"
DEGRADED = "degraded"
DEAD = "dead"

DEGRADE_AFTER_FAILURES = 5
COOLOFF_SECONDS = 30 * 60
CACHE_TTL = 60


@dataclass
class SourceHealthRecord:
    source_name: str
    last_success_at: datetime | None
    last_failure_at: datetime | None
    consecutive_failures: int
    status: str
    last_error: str | None
    last_http_status: int | None
    updated_at: datetime | None


class SourceHealthRepository:
    """Per-service source-health tracker with Redis-backed circuit state cache."""

    def __init__(
        self,
        *,
        service: str,
        table,  # SQLAlchemy Table or ORM model class (will resolve __table__)
        session_factory,
        cache: Cache,
    ) -> None:
        self._service = service
        # Accept either a Table or an ORM mapped class
        self._table = getattr(table, "__table__", table)
        self._session_factory = session_factory
        self._cache = cache

    def _cache_key(self, source: str) -> str:
        return f"health:{self._service}:{source}"

    async def is_open(self, source: str) -> bool:
        cached = await self._cache.get_json(self._cache_key(source))
        if cached is not None:
            status = cached.get("status")
            if status == DEGRADED:
                degraded_at = cached.get("degraded_at")
                if degraded_at is None:
                    return True
                age = (
                    datetime.now(timezone.utc)
                    - datetime.fromisoformat(degraded_at)
                ).total_seconds()
                return age < COOLOFF_SECONDS
            if status == DEAD:
                return True
            return False
        record = await self._fetch(source)
        if record is None:
            return False
        return await self._cache_and_check(record)

    async def mark_success(self, source: str, http_status: int | None = None) -> None:
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            stmt = (
                insert(self._table)
                .values(
                    source_name=source,
                    last_success_at=now,
                    consecutive_failures=0,
                    status=ACTIVE,
                    last_error=None,
                    last_http_status=http_status,
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=["source_name"],
                    set_={
                        "last_success_at": now,
                        "consecutive_failures": 0,
                        "status": ACTIVE,
                        "last_error": None,
                        "last_http_status": http_status,
                        "updated_at": now,
                    },
                )
            )
            await session.execute(stmt)
            await session.commit()
        await self._cache.set_json(
            self._cache_key(source), {"status": ACTIVE}, ttl_seconds=CACHE_TTL
        )

    async def mark_failure(
        self, source: str, error: str, http_status: int | None = None
    ) -> None:
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            existing = await session.execute(
                select(self._table).where(self._table.c.source_name == source)
            )
            row = existing.first()
            consecutive = (row.consecutive_failures if row else 0) + 1
            status = DEGRADED if consecutive >= DEGRADE_AFTER_FAILURES else ACTIVE
            stmt = (
                insert(self._table)
                .values(
                    source_name=source,
                    last_failure_at=now,
                    consecutive_failures=consecutive,
                    status=status,
                    last_error=error[:2048],
                    last_http_status=http_status,
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=["source_name"],
                    set_={
                        "last_failure_at": now,
                        "consecutive_failures": consecutive,
                        "status": status,
                        "last_error": error[:2048],
                        "last_http_status": http_status,
                        "updated_at": now,
                    },
                )
            )
            await session.execute(stmt)
            await session.commit()
        cache_payload = {"status": status}
        if status == DEGRADED:
            cache_payload["degraded_at"] = now.isoformat()
        await self._cache.set_json(self._cache_key(source), cache_payload, ttl_seconds=CACHE_TTL)
        if status == DEGRADED:
            logger.warning(
                "source_degraded", service=self._service, source=source, error=error
            )

    async def get_all(self) -> list[SourceHealthRecord]:
        async with self._session_factory() as session:
            result = await session.execute(select(self._table).order_by(self._table.c.source_name))
            rows = result.fetchall()
        return [
            SourceHealthRecord(
                source_name=r.source_name,
                last_success_at=r.last_success_at,
                last_failure_at=r.last_failure_at,
                consecutive_failures=r.consecutive_failures,
                status=r.status,
                last_error=r.last_error,
                last_http_status=r.last_http_status,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    async def _fetch(self, source: str) -> SourceHealthRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(self._table).where(self._table.c.source_name == source)
            )
            r = result.first()
        if r is None:
            return None
        return SourceHealthRecord(
            source_name=r.source_name,
            last_success_at=r.last_success_at,
            last_failure_at=r.last_failure_at,
            consecutive_failures=r.consecutive_failures,
            status=r.status,
            last_error=r.last_error,
            last_http_status=r.last_http_status,
            updated_at=r.updated_at,
        )

    async def _cache_and_check(self, record: SourceHealthRecord) -> bool:
        payload: dict[str, str] = {"status": record.status}
        if record.status == DEGRADED and record.last_failure_at is not None:
            payload["degraded_at"] = record.last_failure_at.isoformat()
        await self._cache.set_json(
            self._cache_key(record.source_name), payload, ttl_seconds=CACHE_TTL
        )
        if record.status == DEAD:
            return True
        if record.status == DEGRADED and record.last_failure_at is not None:
            age = (
                datetime.now(timezone.utc) - record.last_failure_at
            ).total_seconds()
            return age < COOLOFF_SECONDS
        return False
