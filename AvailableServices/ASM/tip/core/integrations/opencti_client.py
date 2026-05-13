"""
OpenCTI GraphQL API client.

Provides methods for creating indicators, vulnerabilities,
reports, and relationships in OpenCTI via its GraphQL endpoint.
"""
from typing import Any, Dict, List, Optional

import requests

from tip.core.config import settings
from tip.core.logger import get_logger

logger = get_logger(__name__)


class OpenCTIClient:
    """Lightweight OpenCTI GraphQL client."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.base_url = (base_url or settings.OPENCTI_URL).rstrip("/")
        self.api_key = api_key or settings.OPENCTI_API_KEY
        self.graphql_url = f"{self.base_url}/graphql"

    # ── helpers ──────────────────────────────────────────────────

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _query(self, query: str, variables: Optional[Dict] = None) -> Dict:
        body: Dict[str, Any] = {"query": query}
        if variables:
            body["variables"] = variables
        resp = requests.post(
            self.graphql_url,
            headers=self._headers,
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            logger.error("OpenCTI GraphQL errors: %s", data["errors"])
        return data.get("data", {})

    # ── Indicators ───────────────────────────────────────────────

    def create_indicator(
        self,
        name: str,
        pattern: str,
        pattern_type: str = "stix",
        description: str = "",
        valid_from: Optional[str] = None,
    ) -> Dict:
        """Create a STIX Indicator object."""
        mutation = """
        mutation CreateIndicator($input: IndicatorAddInput!) {
            indicatorAdd(input: $input) {
                id
                name
                pattern
                pattern_type
            }
        }
        """
        variables = {
            "input": {
                "name": name,
                "pattern": pattern,
                "pattern_type": pattern_type,
                "description": description,
                "x_opencti_main_observable_type": "StixFile",
            }
        }
        if valid_from:
            variables["input"]["valid_from"] = valid_from
        result = self._query(mutation, variables)
        return result.get("indicatorAdd", result)

    def search_indicators(self, value: str, limit: int = 50) -> List[Dict]:
        query = """
        query SearchIndicators($search: String, $first: Int) {
            indicators(search: $search, first: $first) {
                edges {
                    node { id name pattern pattern_type description }
                }
            }
        }
        """
        result = self._query(query, {"search": value, "first": limit})
        edges = result.get("indicators", {}).get("edges", [])
        return [e["node"] for e in edges]

    # ── Vulnerabilities ──────────────────────────────────────────

    def create_vulnerability(self, cve_id: str, description: str = "") -> Dict:
        mutation = """
        mutation CreateVuln($input: VulnerabilityAddInput!) {
            vulnerabilityAdd(input: $input) {
                id
                name
                description
            }
        }
        """
        variables = {
            "input": {
                "name": cve_id,
                "description": description,
            }
        }
        result = self._query(mutation, variables)
        return result.get("vulnerabilityAdd", result)

    # ── Reports ──────────────────────────────────────────────────

    def create_report(
        self,
        name: str,
        description: str = "",
        published: Optional[str] = None,
        object_refs: Optional[List[str]] = None,
    ) -> Dict:
        mutation = """
        mutation CreateReport($input: ReportAddInput!) {
            reportAdd(input: $input) {
                id
                name
                description
            }
        }
        """
        variables: Dict[str, Any] = {
            "input": {
                "name": name,
                "description": description,
                "published": published or "2026-01-01T00:00:00Z",
            }
        }
        if object_refs:
            variables["input"]["objects"] = object_refs
        result = self._query(mutation, variables)
        return result.get("reportAdd", result)

    # ── Relationships ────────────────────────────────────────────

    def create_relationship(
        self,
        from_id: str,
        to_id: str,
        relationship_type: str = "related-to",
    ) -> Dict:
        mutation = """
        mutation CreateRelationship($input: StixCoreRelationshipAddInput!) {
            stixCoreRelationshipAdd(input: $input) {
                id
                relationship_type
            }
        }
        """
        variables = {
            "input": {
                "fromId": from_id,
                "toId": to_id,
                "relationship_type": relationship_type,
            }
        }
        result = self._query(mutation, variables)
        return result.get("stixCoreRelationshipAdd", result)
