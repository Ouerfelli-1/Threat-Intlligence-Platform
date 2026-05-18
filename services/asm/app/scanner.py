"""
Orchestrates a passive discovery scan for all active scopes.
Creates a Job, enumerates subdomains from passive sources, stores findings.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tip_source_health import SourceHealthRepository

from app.discovery.passive import passive_subdomain_enum
from app.models import Finding, Job, Scope, Target

log = logging.getLogger(__name__)


async def run_scan(session_factory, health: SourceHealthRepository, shodan_api_key: str = "") -> dict:
    async with session_factory() as session:
        scopes_result = await session.execute(select(Scope).where(Scope.active.is_(True)))
        scopes = scopes_result.scalars().all()

    total_findings = 0
    for scope in scopes:
        async with session_factory() as session:
            findings = await _scan_scope(session, scope, health, shodan_api_key)
            total_findings += findings

    log.info("asm_scan complete total_findings=%d scopes=%d", total_findings, len(scopes))
    return {"scopes": len(scopes), "findings": total_findings}


async def _scan_scope(
    session: AsyncSession, scope: Scope, health: SourceHealthRepository, shodan_api_key: str
) -> int:
    job = Job(
        id=uuid.uuid4(),
        scope_id=scope.id,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    session.add(job)
    await session.flush()

    # Only scan active targets — `active=false` means the analyst paused this
    # specific entry (the scope itself was already filtered to active in run_scan).
    targets_result = await session.execute(
        select(Target).where(
            Target.scope_id == scope.id,
            Target.type == "domain",
            Target.active.is_(True),
        )
    )
    domains = [t.value for t in targets_result.scalars().all()]

    findings_count = 0
    errors = []

    for domain in domains:
        try:
            subdomains = await passive_subdomain_enum(domain)
            await health.mark_success(f"passive-subdomain-{domain}")

            for sub in subdomains:
                finding = Finding(
                    id=uuid.uuid4(),
                    job_id=job.id,
                    target_id=None,
                    type="subdomain",
                    value=sub,
                    source="passive-multi",
                    discovered_at=datetime.now(timezone.utc),
                    details={"root_domain": domain},
                )
                session.add(finding)
                findings_count += 1

        except Exception as exc:
            log.error("asm scope=%s domain=%s error=%s", scope.id, domain, exc)
            errors.append(str(exc))
            await health.mark_failure(f"passive-subdomain-{domain}", str(exc))

    job.status = "completed" if not errors else "partial"
    job.completed_at = datetime.now(timezone.utc)
    job.findings_count = findings_count
    if errors:
        job.error = "; ".join(errors[:3])

    await session.commit()
    return findings_count
