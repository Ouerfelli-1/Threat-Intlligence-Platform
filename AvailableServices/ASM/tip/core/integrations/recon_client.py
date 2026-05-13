"""
Client for the existing Recon Findings API (port 8001).

This lets the TIP read reconnaissance data (subdomains, ports, CVEs,
services) that was collected by the existing ASM engine, without
touching its database directly.
"""
from typing import Any, Dict, List, Optional

import requests

from tip.core.config import settings
from tip.core.logger import get_logger

logger = get_logger(__name__)


class ReconClient:
    """HTTP client for the existing recon findings API."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.RECON_FINDINGS_API_URL).rstrip("/")

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        resp = requests.get(
            f"{self.base_url}{endpoint}",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Global ───────────────────────────────────────────────────

    def health(self) -> Dict:
        return self._get("/health")

    def get_summary(self) -> Dict:
        return self._get("/api/v1/summary")

    def get_scope_stats(self) -> List[Dict]:
        return self._get("/api/v1/stats/scopes")

    # ── Scope-level queries ──────────────────────────────────────

    def get_scope_findings(
        self,
        scope_id: str,
        page: int = 1,
        per_page: int = 100,
        finding_type: Optional[str] = None,
    ) -> Dict:
        params: Dict[str, Any] = {"page": page, "per_page": per_page}
        if finding_type:
            params["finding_type"] = finding_type
        return self._get(f"/api/v1/scopes/{scope_id}/findings", params)

    def get_scope_summary(self, scope_id: str) -> Dict:
        return self._get(f"/api/v1/scopes/{scope_id}/summary")

    def get_scope_subdomains(self, scope_id: str) -> Dict:
        return self._get(f"/api/v1/scopes/{scope_id}/subdomains")

    def get_scope_dns(self, scope_id: str) -> Dict:
        return self._get(f"/api/v1/scopes/{scope_id}/dns")

    def get_scope_cves(
        self,
        scope_id: str,
        severity: Optional[str] = None,
        min_cvss: Optional[float] = None,
    ) -> Dict:
        params: Dict[str, Any] = {}
        if severity:
            params["severity"] = severity
        if min_cvss is not None:
            params["min_cvss"] = min_cvss
        return self._get(f"/api/v1/scopes/{scope_id}/cves", params)

    def get_scope_critical_cves(self, scope_id: str) -> Dict:
        return self._get(f"/api/v1/scopes/{scope_id}/cves/critical")

    def get_scope_ports(self, scope_id: str) -> Dict:
        return self._get(f"/api/v1/scopes/{scope_id}/ports")

    def get_scope_services(self, scope_id: str) -> Dict:
        return self._get(f"/api/v1/scopes/{scope_id}/services")

    def get_scope_vulnerable_services(self, scope_id: str) -> Dict:
        return self._get(f"/api/v1/scopes/{scope_id}/vulnerable-services")

    # ── Job-level queries ────────────────────────────────────────

    def get_job_findings(self, job_id: str) -> Dict:
        return self._get(f"/api/v1/jobs/{job_id}/findings")

    def get_job_summary(self, job_id: str) -> Dict:
        return self._get(f"/api/v1/jobs/{job_id}/summary")

    def get_job_cves(self, job_id: str) -> Dict:
        return self._get(f"/api/v1/jobs/{job_id}/cves")

    # ── Search ───────────────────────────────────────────────────

    def search(self, query: str) -> Dict:
        return self._get("/api/v1/search", params={"q": query})
