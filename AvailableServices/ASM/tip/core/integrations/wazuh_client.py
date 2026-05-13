"""
Wazuh REST API client.

Provides methods for:
  - Authentication (JWT)
  - Agent management
  - Syscollector (software inventory, OS, ports, processes)
  - Vulnerability detection results
  - Security alerts
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
import urllib3

from tip.core.config import settings
from tip.core.logger import get_logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = get_logger(__name__)


class WazuhClient:
    """Client for the Wazuh Manager REST API (v4)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        verify_ssl: Optional[bool] = None,
    ):
        self.base_url = (base_url or settings.WAZUH_API_URL).rstrip("/")
        self.username = username or settings.WAZUH_API_USER
        self.password = password or settings.WAZUH_API_PASSWORD
        self.verify_ssl = verify_ssl if verify_ssl is not None else settings.WAZUH_VERIFY_SSL
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None

    # ── Authentication ───────────────────────────────────────────

    def authenticate(self) -> str:
        """Authenticate and cache a JWT token (valid ~900 s)."""
        if self._token and self._token_expires and datetime.now(timezone.utc) < self._token_expires:
            return self._token

        resp = requests.post(
            f"{self.base_url}/security/user/authenticate",
            auth=(self.username, self.password),
            verify=self.verify_ssl,
            timeout=15,
        )
        resp.raise_for_status()
        self._token = resp.json()["data"]["token"]
        self._token_expires = datetime.now(timezone.utc) + timedelta(seconds=850)
        logger.debug("Wazuh: authenticated successfully")
        return self._token

    # ── Generic request helper ───────────────────────────────────

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.authenticate()}",
            "Content-Type": "application/json",
        }
        resp = requests.request(
            method,
            f"{self.base_url}{endpoint}",
            headers=headers,
            verify=self.verify_ssl,
            timeout=30,
            **kwargs,
        )
        resp.raise_for_status()
        return resp.json()

    def _items(self, data: Dict) -> List[Dict]:
        return data.get("data", {}).get("affected_items", [])

    # ── Agent operations ─────────────────────────────────────────

    def get_agents(self, status: Optional[str] = None) -> List[Dict]:
        params: Dict[str, Any] = {}
        if status:
            params["status"] = status
        return self._items(self._request("GET", "/agents", params=params))

    def get_agent_by_ip(self, ip: str) -> Optional[Dict]:
        items = self._items(self._request("GET", f"/agents?ip={ip}"))
        return items[0] if items else None

    def get_agent_by_id(self, agent_id: str) -> Optional[Dict]:
        items = self._items(self._request("GET", f"/agents?agents_list={agent_id}"))
        return items[0] if items else None

    # ── Syscollector (software inventory) ────────────────────────

    def get_agent_packages(self, agent_id: str) -> List[Dict]:
        return self._items(self._request("GET", f"/syscollector/{agent_id}/packages"))

    def get_agent_os(self, agent_id: str) -> Optional[Dict]:
        items = self._items(self._request("GET", f"/syscollector/{agent_id}/os"))
        return items[0] if items else None

    def get_agent_hardware(self, agent_id: str) -> Optional[Dict]:
        items = self._items(self._request("GET", f"/syscollector/{agent_id}/hardware"))
        return items[0] if items else None

    def get_agent_ports(self, agent_id: str) -> List[Dict]:
        return self._items(self._request("GET", f"/syscollector/{agent_id}/ports"))

    def get_agent_processes(self, agent_id: str) -> List[Dict]:
        return self._items(self._request("GET", f"/syscollector/{agent_id}/processes"))

    # ── Vulnerability detection ──────────────────────────────────

    def get_agent_vulnerabilities(self, agent_id: str) -> List[Dict]:
        return self._items(self._request("GET", f"/vulnerability/{agent_id}"))

    # ── Alerts ───────────────────────────────────────────────────

    def get_alerts(
        self,
        agent_id: Optional[str] = None,
        rule_id: Optional[int] = None,
        level_min: int = 0,
        limit: int = 100,
    ) -> List[Dict]:
        params: Dict[str, Any] = {"limit": limit, "sort": "-timestamp"}
        if agent_id:
            params["agent_id"] = agent_id
        if rule_id:
            params["rule_id"] = rule_id
        if level_min > 0:
            params["level"] = f">={level_min}"
        return self._items(self._request("GET", "/alerts", params=params))

    def search_alerts(self, query: str, limit: int = 100) -> List[Dict]:
        return self._items(
            self._request("GET", "/alerts", params={"q": query, "limit": limit})
        )
