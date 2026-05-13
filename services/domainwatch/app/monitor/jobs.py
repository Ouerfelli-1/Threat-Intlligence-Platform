"""
Orchestrates periodic monitoring for all active domains.
Ported from AvailableServices/Domain Watcher/scripts/jobs.py — core pipeline kept;
embedded scheduler, Jinja2 templates, auth, and SQLite removed.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Change, Domain, DomainSubdomain, Snapshot
from app.monitor.check import check_domain, diff_dns

log = logging.getLogger(__name__)


async def run_check_cycle(session_factory, screenshot_dir: str) -> dict:
    async with session_factory() as session:
        domains_result = await session.execute(select(Domain).where(Domain.active.is_(True)))
        domains = domains_result.scalars().all()

    total = {"checked": 0, "changes": 0, "errors": 0}
    for domain in domains:
        try:
            async with session_factory() as session:
                result = await _monitor_domain(session, domain, screenshot_dir)
                total["checked"] += 1
                total["changes"] += result["changes"]
        except Exception as exc:
            log.error("domainwatch domain=%s error=%s", domain.name, exc)
            total["errors"] += 1

    log.info("domainwatch cycle checked=%d changes=%d errors=%d", total["checked"], total["changes"], total["errors"])
    return total


async def _monitor_domain(session: AsyncSession, domain: Domain, screenshot_dir: str) -> dict:
    # Fetch previous snapshot for comparison
    prev_result = await session.execute(
        select(Snapshot)
        .where(Snapshot.domain_id == domain.id)
        .order_by(Snapshot.captured_at.desc())
        .limit(1)
    )
    prev_snapshot = prev_result.scalar_one_or_none()

    # Run all checks
    details = await check_domain(domain.name, screenshot_dir)

    # Save new snapshot
    snapshot = Snapshot(
        id=uuid.uuid4(),
        domain_id=domain.id,
        captured_at=datetime.now(timezone.utc),
        details=details,
        content_hash=details.get("content_hash"),
        screenshot_path=details.get("screenshot_path"),
    )
    session.add(snapshot)

    # Detect changes vs previous snapshot
    changes_found = 0
    if prev_snapshot and prev_snapshot.details:
        diffs = diff_dns(prev_snapshot.details, details)
        for diff in diffs:
            change = Change(
                id=uuid.uuid4(),
                domain_id=domain.id,
                detected_at=datetime.now(timezone.utc),
                change_type=diff["type"],
                before=diff["before"],
                after=diff["after"],
            )
            session.add(change)
            changes_found += 1

    # Update last_checked_at
    domain.last_checked_at = datetime.now(timezone.utc)

    await session.commit()
    return {"changes": changes_found}
