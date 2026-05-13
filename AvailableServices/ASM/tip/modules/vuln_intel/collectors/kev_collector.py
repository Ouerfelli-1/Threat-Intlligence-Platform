"""
CISA Known Exploited Vulnerabilities (KEV) Collector.

Downloads the CISA KEV catalog and marks matching CVEs
in the TIP database.
"""
from typing import Dict, List, Set

import requests
from sqlalchemy.orm import Session

from tip.core.logger import get_logger
from tip.core.models import CVE

logger = get_logger(__name__)

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"


class KEVCollector:
    """Fetch and process the CISA KEV catalog."""

    def __init__(self, db: Session):
        self.db = db

    def fetch_kev_catalog(self) -> List[Dict]:
        """Download the full KEV JSON catalog."""
        resp = requests.get(KEV_URL, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        vulnerabilities = data.get("vulnerabilities", [])
        logger.info("KEV: fetched %d entries from CISA catalog", len(vulnerabilities))
        return vulnerabilities

    def get_kev_cve_ids(self) -> Set[str]:
        """Return a set of CVE IDs present in the KEV catalog."""
        entries = self.fetch_kev_catalog()
        return {entry.get("cveID") for entry in entries if entry.get("cveID")}

    def mark_kev_cves(self) -> int:
        """
        Fetch the KEV catalog and set ``is_in_cisa_kev = True``
        for every matching CVE in the database.

        Returns:
            Number of CVEs updated.
        """
        kev_ids = self.get_kev_cve_ids()
        if not kev_ids:
            return 0

        cves = self.db.query(CVE).filter(CVE.cve_id.in_(kev_ids)).all()
        count = 0
        for cve in cves:
            if not cve.is_in_cisa_kev:
                cve.is_in_cisa_kev = True
                cve.has_exploit = True
                count += 1

        self.db.commit()
        logger.info("KEV: marked %d CVEs as CISA KEV", count)
        return count
