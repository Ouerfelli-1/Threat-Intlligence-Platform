"""
CVE Database Service.

Responsible for ingesting parsed CVE data into the ``cves``
table with proper deduplication and query helpers.
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from tip.core.logger import get_logger
from tip.core.models import CVE

logger = get_logger(__name__)


class CVEService:
    """CRUD and query helpers for the CVE table."""

    def __init__(self, db: Session):
        self.db = db

    # ── ingestion ────────────────────────────────────────────────

    def ingest_cve(self, parsed: Dict) -> CVE:
        """
        Insert or update a single CVE record.

        Args:
            parsed: Dict produced by ``NVDCollector.parse_cve()``.

        Returns:
            The CVE ORM instance (new or updated).
        """
        cve_id = parsed.get("cve_id")
        if not cve_id:
            raise ValueError("parsed CVE dict must contain 'cve_id'")

        existing = self.db.query(CVE).filter(CVE.cve_id == cve_id).first()

        if existing:
            # update mutable fields
            for field in (
                "description",
                "cvss_v3_score",
                "cvss_v3_vector",
                "severity",
                "affected_cpe",
                "has_exploit",
                "exploit_references",
                "last_modified",
            ):
                val = parsed.get(field)
                if val is not None:
                    setattr(existing, field, val)
            return existing

        cve = CVE(
            cve_id=cve_id,
            description=parsed.get("description"),
            cvss_v3_score=parsed.get("cvss_v3_score"),
            cvss_v3_vector=parsed.get("cvss_v3_vector"),
            severity=parsed.get("severity"),
            affected_cpe=parsed.get("affected_cpe"),
            has_exploit=parsed.get("has_exploit", False),
            exploit_references=parsed.get("exploit_references"),
            published_date=(
                datetime.fromisoformat(parsed["published_date"])
                if parsed.get("published_date")
                else None
            ),
            last_modified=(
                datetime.fromisoformat(parsed["last_modified"])
                if parsed.get("last_modified")
                else None
            ),
        )
        self.db.add(cve)
        self.db.flush()
        return cve

    def ingest_batch(self, parsed_list: List[Dict]) -> int:
        """Ingest a list of parsed CVEs. Returns count of new records."""
        count = 0
        for p in parsed_list:
            try:
                cve = self.ingest_cve(p)
                if cve.id is None:  # newly added (not yet flushed)
                    count += 1
            except Exception as exc:
                logger.error("Error ingesting CVE %s: %s", p.get("cve_id"), exc)
        self.db.commit()
        logger.info("Ingested batch: %d new CVEs out of %d", count, len(parsed_list))
        return count

    # ── queries ──────────────────────────────────────────────────

    def get_cve(self, cve_id: str) -> Optional[CVE]:
        return self.db.query(CVE).filter(CVE.cve_id == cve_id).first()

    def get_cves_by_severity(self, severity: str) -> List[CVE]:
        return self.db.query(CVE).filter(CVE.severity == severity.upper()).all()

    def get_recent_cves(self, days: int = 7) -> List[CVE]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return self.db.query(CVE).filter(CVE.created_at >= cutoff).all()

    def get_critical_and_high(self) -> List[CVE]:
        return (
            self.db.query(CVE)
            .filter(CVE.severity.in_(["CRITICAL", "HIGH"]))
            .order_by(CVE.cvss_v3_score.desc())
            .all()
        )

    def get_kev_cves(self) -> List[CVE]:
        return self.db.query(CVE).filter(CVE.is_in_cisa_kev.is_(True)).all()
