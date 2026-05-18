import asyncio
import logging

from tip_source_health import SourceHealthRepository

from app.sources.mitre_attack import sync_mitre_attack
from app.sources.ransomware_live import (
    correlate_groups_to_actors,
    sync_ransomware_groups,
    sync_ransomware_victims,
    sync_ransomware_victims_full,
)

log = logging.getLogger(__name__)


async def run_refresh_cycle(session_factory, health: SourceHealthRepository) -> dict:
    results = {}

    async def _run(name: str, coro):
        try:
            results[name] = await coro
        except Exception as exc:
            log.error("refresh_cycle source=%s error=%s", name, exc)
            results[name] = 0

    async with session_factory() as session:
        tasks = [
            _run("mitre_attack", sync_mitre_attack(session, health)),
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async with session_factory() as session:
        tasks = [
            _run("ransomware_groups", sync_ransomware_groups(session, health)),
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async with session_factory() as session:
        tasks = [
            _run("ransomware_victims", sync_ransomware_victims(session, health)),
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    # Correlate ransomware groups -> MITRE actors after both have been refreshed
    async with session_factory() as session:
        try:
            results["actor_correlation"] = await correlate_groups_to_actors(session)
        except Exception as exc:
            log.error("refresh_cycle correlation_error=%s", exc)
            results["actor_correlation"] = 0

    log.info("refresh_cycle complete results=%s", results)
    return results


async def run_full_refresh_cycle(session_factory, health: SourceHealthRepository) -> dict:
    """Heavy seed cycle: MITRE + ALL ransomware groups + ALL historical victims."""
    results = {}

    async def _run(name: str, coro):
        try:
            results[name] = await coro
        except Exception as exc:
            log.error("full_refresh source=%s error=%s", name, exc)
            results[name] = 0

    async with session_factory() as session:
        await _run("mitre_attack", sync_mitre_attack(session, health))

    async with session_factory() as session:
        await _run("ransomware_groups", sync_ransomware_groups(session, health))

    async with session_factory() as session:
        await _run("ransomware_victims_full", sync_ransomware_victims_full(session, health))

    async with session_factory() as session:
        try:
            results["actor_correlation"] = await correlate_groups_to_actors(session)
        except Exception as exc:
            log.error("full_refresh correlation_error=%s", exc)
            results["actor_correlation"] = 0

    log.info("full_refresh_cycle complete results=%s", results)
    return results
