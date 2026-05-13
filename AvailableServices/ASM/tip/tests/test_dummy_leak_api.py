"""
Unit tests for the Dummy Leak API.
"""
import pytest
from fastapi.testclient import TestClient

from tip.dummy_leak_api.main import app, LEAKS

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_leaks():
    """Ensure tests don't leak state."""
    original = list(LEAKS)
    yield
    LEAKS.clear()
    LEAKS.extend(original)


class TestDummyLeakHealth:
    def test_root(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["service"] == "Dummy Leak API"


class TestGetLeaks:
    def test_get_all_leaks(self):
        resp = client.get("/api/v1/leaks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == len(LEAKS)
        assert len(data["leaks"]) == data["total"]

    def test_get_leak_by_id(self):
        resp = client.get("/api/v1/leaks/leak-001")
        assert resp.status_code == 200
        assert resp.json()["source"] == "DarkMarket Forums"

    def test_get_leak_not_found(self):
        resp = client.get("/api/v1/leaks/nonexistent")
        assert resp.status_code == 404


class TestSearchLeaks:
    def test_search_by_domain(self):
        resp = client.post("/api/v1/leaks/search", json={
            "domains": ["acmecorp.com"]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for leak in data["leaks"]:
            assert "acmecorp.com" in leak["affected_domains"]

    def test_search_no_results(self):
        resp = client.post("/api/v1/leaks/search", json={
            "domains": ["nonexistent-domain.xyz"]
        })
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_search_by_date(self):
        resp = client.post("/api/v1/leaks/search", json={
            "since": "2026-02-20T00:00:00Z"
        })
        assert resp.status_code == 200
        # Should only include leaks from 2026-02-20 onwards
        for leak in resp.json()["leaks"]:
            assert leak["discovered_date"] >= "2026-02-20"

    def test_search_empty_query_returns_all(self):
        resp = client.post("/api/v1/leaks/search", json={})
        assert resp.status_code == 200
        assert resp.json()["total"] == len(LEAKS)


class TestAddLeak:
    def test_add_leak(self):
        new_leak = {
            "source": "Test Source",
            "type": "credentials",
            "affected_domains": ["pytest.example.com"],
            "affected_emails": ["test@pytest.example.com"],
            "record_count": 42,
            "contains_passwords": True,
            "severity": "LOW",
        }
        resp = client.post("/api/v1/leaks", json=new_leak)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "created"
        assert data["leak"]["source"] == "Test Source"
        assert "id" in data["leak"]
        assert "discovered_date" in data["leak"]

    def test_added_leak_appears_in_list(self):
        original_count = len(LEAKS)
        client.post("/api/v1/leaks", json={
            "source": "Test", "type": "credentials",
            "affected_domains": ["x.com"],
        })
        resp = client.get("/api/v1/leaks")
        assert resp.json()["total"] == original_count + 1
