"""
TIP Scheduler — periodic background tasks.

Uses APScheduler to run recurring jobs:
  - ASM asset sync (from existing recon Findings API)
  - Software inventory sync (Wazuh Syscollector)
  - CVE fetch + matching
  - Data leak checks
  - IDS event ingestion
  - Correlation engine
"""
import signal
import sys
import time
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from tip.core.config import settings
from tip.core.database import SessionLocal, create_all_tables
from tip.core.logger import get_logger
from tip.core.models import Organization

logger = get_logger("tip.scheduler")


# ── Job functions ────────────────────────────────────────────────

def job_sync_assets():
    """Sync assets from recon Findings API for every organization."""
    from tip.modules.asm.asset_service import AssetService

    db = SessionLocal()
    try:
        svc = AssetService(db)
        for org in db.query(Organization).all():
            if not org.recon_scope_id:
                continue
            try:
                synced = svc.sync_assets_from_recon(org)
                logger.info("[ASM] Synced %d assets for %s", len(synced), org.primary_domain)
            except Exception:
                logger.exception("[ASM] Failed for org %s", org.primary_domain)
        db.commit()
    finally:
        db.close()


def job_sync_software():
    """Sync software inventory from Wazuh for all assets."""
    from tip.modules.asm.software_service import SoftwareService

    db = SessionLocal()
    try:
        svc = SoftwareService(db)
        for org in db.query(Organization).all():
            try:
                svc.sync_all_assets_for_org(org.id)
                logger.info("[SW] Software synced for %s", org.primary_domain)
            except Exception:
                logger.exception("[SW] Failed for org %s", org.primary_domain)
        db.commit()
    finally:
        db.close()


def job_fetch_and_match_cves():
    """Fetch recent CVEs and match against asset inventory."""
    from tip.modules.vuln_intel.cve_service import CVEService
    from tip.modules.vuln_intel.matching_service import MatchingService
    from tip.modules.vuln_intel.collectors.nvd_collector import NVDCollector
    from tip.modules.vuln_intel.collectors.kev_collector import KEVCollector

    db = SessionLocal()
    try:
        # 1. Fetch new CVEs from NVD
        collector = NVDCollector()
        raw_cves = collector.fetch_recent_cves(days=settings.CVE_FETCH_DAYS)
        parsed = [collector.parse_cve(r) for r in raw_cves]

        cve_svc = CVEService(db)
        cve_svc.ingest_batch(parsed)
        new_cves = cve_svc.get_recent_cves(days=settings.CVE_FETCH_DAYS)
        logger.info("[CVE] Ingested %d CVEs", len(new_cves))

        # 2. Mark CISA KEV entries
        try:
            kev = KEVCollector(db)
            kev.mark_kev_cves()
        except Exception:
            logger.exception("[CVE] KEV sync failed")

        # 3. Match against all assets
        matcher = MatchingService(db)
        total_alerts = 0
        for cve in new_cves:
            alerts = matcher.scan_all_assets_for_cve(cve)
            total_alerts += len(alerts)
        logger.info("[CVE] Generated %d vulnerability alerts", total_alerts)

        db.commit()
    finally:
        db.close()


def job_check_leaks():
    """Check for new data leaks for every organization."""
    from tip.modules.data_leak.collectors.leak_collector import LeakCollector

    db = SessionLocal()
    try:
        collector = LeakCollector(db)
        for org in db.query(Organization).all():
            try:
                alerts = collector.process_leaks(org)
                if alerts:
                    logger.warning("[LEAK] %d new leak alert(s) for %s", len(alerts), org.primary_domain)
            except Exception:
                logger.exception("[LEAK] Failed for org %s", org.primary_domain)
        db.commit()
    finally:
        db.close()


def job_ingest_ids_events():
    """Ingest IDS events from Wazuh."""
    from tip.modules.ids.alert_service import IDSAlertService

    db = SessionLocal()
    try:
        svc = IDSAlertService(db)
        events = svc.fetch_and_ingest()
        if events:
            alerts = svc.generate_alerts_from_events(events)
            logger.info("[IDS] Ingested %d events, %d alerts", len(events), len(alerts))
        db.commit()
    finally:
        db.close()


def job_run_correlations():
    """Run correlation engine for every organization."""
    from tip.correlation.engine import CorrelationEngine

    db = SessionLocal()
    try:
        engine = CorrelationEngine(db)
        for org in db.query(Organization).all():
            try:
                alerts = engine.run_all(org)
                if alerts:
                    logger.warning("[CORR] %d correlation alert(s) for %s", len(alerts), org.primary_domain)
                # also compute risk score
                risk = engine.calculate_org_risk_score(org)
                logger.info("[CORR] Risk score for %s: %.0f (%s)", org.primary_domain, risk["risk_score"], risk["risk_level"])
            except Exception:
                logger.exception("[CORR] Failed for org %s", org.primary_domain)
        db.commit()
    finally:
        db.close()


# ── Scheduler setup ──────────────────────────────────────────────

def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")

    scheduler.add_job(
        job_sync_assets,
        "interval",
        seconds=settings.SCHEDULE_ASM_SYNC,
        id="sync_assets",
        name="ASM Asset Sync",
        next_run_time=datetime.now(timezone.utc),   # run immediately on start
    )

    scheduler.add_job(
        job_sync_software,
        "interval",
        seconds=settings.SCHEDULE_ASM_SYNC,
        id="sync_software",
        name="Software Inventory Sync",
    )

    scheduler.add_job(
        job_fetch_and_match_cves,
        "interval",
        seconds=settings.SCHEDULE_CVE_FETCH,
        id="fetch_cves",
        name="CVE Fetch & Match",
    )

    scheduler.add_job(
        job_check_leaks,
        "interval",
        seconds=settings.SCHEDULE_LEAK_CHECK,
        id="check_leaks",
        name="Data Leak Check",
    )

    scheduler.add_job(
        job_ingest_ids_events,
        "interval",
        seconds=settings.SCHEDULE_IDS_INGEST,
        id="ingest_ids",
        name="IDS Event Ingestion",
    )

    scheduler.add_job(
        job_run_correlations,
        "interval",
        seconds=settings.SCHEDULE_CORRELATION,
        id="run_correlations",
        name="Correlation Engine",
    )

    return scheduler


def main():
    """Entry-point for the scheduler container."""
    create_all_tables()
    logger.info("TIP Scheduler starting …")

    sched = create_scheduler()
    sched.start()

    # graceful shutdown
    def _shutdown(signum, frame):
        logger.info("Shutting down scheduler …")
        sched.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        sched.shutdown(wait=False)


if __name__ == "__main__":
    main()
