"""
MISP REST API client.

Provides methods for creating / searching events and attributes
using the MISP REST API.  Uses raw ``requests`` calls (no pymisp
dependency) for lighter footprint.
"""
from typing import Any, Dict, List, Optional

import requests
import urllib3

from tip.core.config import settings
from tip.core.logger import get_logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = get_logger(__name__)


class MISPClient:
    """Lightweight MISP REST client."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        verify_ssl: Optional[bool] = None,
    ):
        self.base_url = (base_url or settings.MISP_URL).rstrip("/")
        self.api_key = api_key or settings.MISP_API_KEY
        self.verify_ssl = verify_ssl if verify_ssl is not None else settings.MISP_VERIFY_SSL

    # ── helpers ──────────────────────────────────────────────────

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _post(self, endpoint: str, json_body: Dict) -> Dict:
        resp = requests.post(
            f"{self.base_url}{endpoint}",
            headers=self._headers,
            json=json_body,
            verify=self.verify_ssl,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        resp = requests.get(
            f"{self.base_url}{endpoint}",
            headers=self._headers,
            params=params,
            verify=self.verify_ssl,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Events ───────────────────────────────────────────────────

    def create_event(
        self,
        info: str,
        threat_level_id: int = 2,
        analysis: int = 0,
        distribution: int = 0,
        attributes: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Create a new MISP event.

        Args:
            info: Event description / title.
            threat_level_id: 1=High, 2=Medium, 3=Low, 4=Undefined.
            analysis: 0=Initial, 1=Ongoing, 2=Completed.
            distribution: 0=Org-only, 1=Community, 2=Connected, 3=All.
            attributes: Optional list of attribute dicts to attach.

        Returns:
            Created event dict.
        """
        body: Dict[str, Any] = {
            "Event": {
                "info": info,
                "threat_level_id": str(threat_level_id),
                "analysis": str(analysis),
                "distribution": str(distribution),
            }
        }
        if attributes:
            body["Event"]["Attribute"] = attributes

        result = self._post("/events/add", body)
        logger.info("MISP: event created – %s", result.get("Event", {}).get("id"))
        return result

    def get_event(self, event_id: str) -> Dict:
        return self._get(f"/events/view/{event_id}")

    def search_events(self, value: str, type_attribute: Optional[str] = None) -> List[Dict]:
        body: Dict[str, Any] = {"returnFormat": "json", "value": value}
        if type_attribute:
            body["type_attribute"] = type_attribute
        result = self._post("/events/restSearch", body)
        return result.get("response", [])

    # ── Attributes ───────────────────────────────────────────────

    def add_attribute(
        self,
        event_id: str,
        attr_type: str,
        value: str,
        category: Optional[str] = None,
        to_ids: bool = True,
        comment: Optional[str] = None,
    ) -> Dict:
        """
        Add a single attribute to an existing event.

        Common attr_type values:
          ip-dst, ip-src, domain, hostname, url, email-src,
          vulnerability (for CVE IDs), md5, sha256, filename …
        """
        body: Dict[str, Any] = {
            "type": attr_type,
            "value": value,
            "to_ids": to_ids,
        }
        if category:
            body["category"] = category
        if comment:
            body["comment"] = comment

        return self._post(f"/attributes/add/{event_id}", body)

    def search_attributes(
        self,
        value: Optional[str] = None,
        type_attribute: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        body: Dict[str, Any] = {"returnFormat": "json", "limit": limit}
        if value:
            body["value"] = value
        if type_attribute:
            body["type_attribute"] = type_attribute
        result = self._post("/attributes/restSearch", body)
        return result.get("response", {}).get("Attribute", [])

    # ── Tags ─────────────────────────────────────────────────────

    def tag_event(self, event_id: str, tag: str) -> Dict:
        return self._post(
            f"/events/addTag/{event_id}",
            {"tag": tag},
        )
