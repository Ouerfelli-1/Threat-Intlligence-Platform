"""
NVD (National Vulnerability Database) CVE Collector.

Fetches CVE data from the NVD API v2.0 with proper rate-limiting
and pagination support.
"""
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

from tip.core.config import settings
from tip.core.logger import get_logger

logger = get_logger(__name__)


class NVDCollector:
    """Collect CVE data from the NIST NVD API v2.0."""

    BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.NVD_API_KEY
        self.headers: Dict[str, str] = {}
        if self.api_key:
            self.headers["apiKey"] = self.api_key
        # Rate limit: 0.6 s with key, 6 s without
        self.rate_limit = 0.6 if self.api_key else settings.NVD_RATE_LIMIT
        self._last_request_time: float = 0

    # ── rate limiting ────────────────────────────────────────────

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    # ── fetchers ─────────────────────────────────────────────────

    def fetch_recent_cves(self, days: Optional[int] = None) -> List[Dict]:
        """Fetch CVEs published in the last *days* days."""
        days = days or settings.CVE_FETCH_DAYS
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)

        params: Dict[str, Any] = {
            "pubStartDate": start.strftime("%Y-%m-%dT00:00:00.000"),
            "pubEndDate": end.strftime("%Y-%m-%dT23:59:59.999"),
            "resultsPerPage": 200,
        }

        logger.info("NVD: fetching CVEs from %s to %s", start.date(), end.date())
        return self._paginated_fetch(params)

    def fetch_cve_by_id(self, cve_id: str) -> Optional[Dict]:
        """Fetch a single CVE by its ID (e.g. CVE-2024-12345)."""
        self._wait_for_rate_limit()
        resp = requests.get(
            self.BASE_URL,
            params={"cveId": cve_id},
            headers=self.headers,
            timeout=30,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        vulns = resp.json().get("vulnerabilities", [])
        return vulns[0] if vulns else None

    def fetch_cves_by_cpe(self, cpe: str) -> List[Dict]:
        """Fetch CVEs that affect a given CPE string."""
        params: Dict[str, Any] = {
            "cpeName": cpe,
            "resultsPerPage": 200,
        }
        return self._paginated_fetch(params)

    # ── pagination helper ────────────────────────────────────────

    def _paginated_fetch(self, params: Dict[str, Any]) -> List[Dict]:
        all_cves: List[Dict] = []
        start_index = 0

        while True:
            self._wait_for_rate_limit()
            params["startIndex"] = start_index
            resp = requests.get(
                self.BASE_URL,
                params=params,
                headers=self.headers,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()

            vulns = data.get("vulnerabilities", [])
            if not vulns:
                break

            all_cves.extend(vulns)
            total_results = data.get("totalResults", 0)
            start_index += len(vulns)

            logger.debug("NVD: fetched %d / %d CVEs", start_index, total_results)
            if start_index >= total_results:
                break

        logger.info("NVD: fetched %d CVEs total", len(all_cves))
        return all_cves

    # ── parser ───────────────────────────────────────────────────

    @staticmethod
    def parse_cve(raw_vuln: Dict) -> Dict:
        """
        Parse a single NVD vulnerability entry into a flat dict
        suitable for inserting into the ``cves`` table.
        """
        cve = raw_vuln.get("cve", {})

        # ── CVSS v3.1 ───────────────────────────────────────────
        metrics = cve.get("metrics", {})
        cvss_v31 = metrics.get("cvssMetricV31", [])
        cvss_v3 = cvss_v31[0] if cvss_v31 else None

        cvss_score: Optional[float] = None
        cvss_vector: Optional[str] = None
        severity = "UNKNOWN"

        if cvss_v3:
            cvss_data = cvss_v3.get("cvssData", {})
            cvss_score = cvss_data.get("baseScore")
            cvss_vector = cvss_data.get("vectorString")
            severity = cvss_data.get("baseSeverity", "UNKNOWN")

        # ── affected CPEs ────────────────────────────────────────
        affected_cpe: List[str] = []
        for config in cve.get("configurations", []):
            for node in config.get("nodes", []):
                for cpe_match in node.get("cpeMatch", []):
                    if cpe_match.get("vulnerable", False):
                        criteria = cpe_match.get("criteria")
                        if criteria:
                            affected_cpe.append(criteria)

        # ── description (English) ────────────────────────────────
        description = ""
        for desc in cve.get("descriptions", []):
            if desc.get("lang") == "en":
                description = desc.get("value", "")
                break

        # ── references ───────────────────────────────────────────
        references = [ref.get("url") for ref in cve.get("references", []) if ref.get("url")]

        # ── exploit flags ────────────────────────────────────────
        has_exploit = any(
            "Exploit" in (ref.get("tags") or [])
            for ref in cve.get("references", [])
        )

        return {
            "cve_id": cve.get("id"),
            "description": description,
            "cvss_v3_score": cvss_score,
            "cvss_v3_vector": cvss_vector,
            "severity": severity,
            "affected_cpe": affected_cpe,
            "has_exploit": has_exploit,
            "exploit_references": references if has_exploit else [],
            "published_date": cve.get("published"),
            "last_modified": cve.get("lastModified"),
        }
