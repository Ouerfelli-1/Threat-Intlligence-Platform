"""
Unit tests for the TIP REST API (FastAPI endpoints).

Uses FastAPI TestClient with SQLite override for the DB dependency.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tip.core.database import Base
from tip.api.main import app, get_db


# ── Override database for API tests ──────────────────────────────

_engine = create_engine(
    "sqlite:///:memory:",
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

@event.listens_for(_engine, "connect")
def _set_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

import tip.core.models  # noqa: F401
Base.metadata.create_all(bind=_engine)
_SessionLocal = sessionmaker(bind=_engine)


def _override_get_db():
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()


app.dependency_overrides[get_db] = _override_get_db

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _reset_tables():
    """Drop & recreate tables between tests for isolation."""
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    yield


# ── Health ───────────────────────────────────────────────────────

class TestHealth:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ── Organizations ────────────────────────────────────────────────

class TestOrganizations:
    def test_create_organization(self):
        resp = client.post("/api/v1/organizations", json={
            "name": "TestCorp", "primary_domain": "test.com"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "TestCorp"
        assert data["primary_domain"] == "test.com"

    def test_list_organizations(self):
        client.post("/api/v1/organizations", json={"name": "A", "primary_domain": "a.com"})
        client.post("/api/v1/organizations", json={"name": "B", "primary_domain": "b.com"})
        resp = client.get("/api/v1/organizations")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_organization(self):
        create_resp = client.post("/api/v1/organizations", json={"name": "X", "primary_domain": "x.com"})
        org_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/organizations/{org_id}")
        assert resp.status_code == 200
        assert resp.json()["primary_domain"] == "x.com"

    def test_get_organization_not_found(self):
        resp = client.get("/api/v1/organizations/999")
        assert resp.status_code == 404

    def test_create_duplicate_domain(self):
        client.post("/api/v1/organizations", json={"name": "A", "primary_domain": "dup.com"})
        resp = client.post("/api/v1/organizations", json={"name": "B", "primary_domain": "dup.com"})
        assert resp.status_code == 409

    def test_delete_organization(self):
        create = client.post("/api/v1/organizations", json={"name": "Del", "primary_domain": "del.com"})
        org_id = create.json()["id"]
        resp = client.delete(f"/api/v1/organizations/{org_id}")
        assert resp.status_code == 204

        # Verify deleted
        resp = client.get(f"/api/v1/organizations/{org_id}")
        assert resp.status_code == 404


# ── Assets ───────────────────────────────────────────────────────

class TestAssets:
    def _create_org_with_asset(self):
        org_resp = client.post("/api/v1/organizations", json={"name": "Org", "primary_domain": "org.com"})
        org_id = org_resp.json()["id"]
        # Directly insert an asset via DB
        session = _SessionLocal()
        from tip.core.models import Asset
        asset = Asset(
            organization_id=org_id, asset_type="service",
            hostname="web.org.com", ip_address="10.0.0.1",
            port=443, is_active=True, risk_score=5.0,
        )
        session.add(asset)
        session.commit()
        session.close()
        return org_id

    def test_list_assets(self):
        org_id = self._create_org_with_asset()
        resp = client.get(f"/api/v1/organizations/{org_id}/assets")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["hostname"] == "web.org.com"


# ── Alerts ───────────────────────────────────────────────────────

class TestAlerts:
    def _seed_alert(self):
        session = _SessionLocal()
        from tip.core.models import Alert
        alert = Alert(
            source_module="vuln_intel",
            alert_type="cve_match",
            severity="HIGH",
            title="Test alert",
            priority=2,
        )
        session.add(alert)
        session.commit()
        alert_id = alert.id
        session.close()
        return alert_id

    def test_list_all_alerts(self):
        self._seed_alert()
        resp = client.get("/api/v1/alerts")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_filter_alerts_by_severity(self):
        self._seed_alert()
        resp = client.get("/api/v1/alerts?severity=HIGH")
        assert resp.status_code == 200
        for a in resp.json():
            assert a["severity"] == "HIGH"

    def test_update_alert_status(self):
        alert_id = self._seed_alert()
        resp = client.patch(f"/api/v1/alerts/{alert_id}", json={"status": "acknowledged"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "acknowledged"

    def test_update_alert_not_found(self):
        resp = client.patch("/api/v1/alerts/999", json={"status": "resolved"})
        assert resp.status_code == 404


# ── CVE Browse ───────────────────────────────────────────────────

class TestCVEBrowse:
    def _seed_cves(self):
        session = _SessionLocal()
        from tip.core.models import CVE
        session.add(CVE(cve_id="CVE-2026-A001", severity="CRITICAL", cvss_v3_score=9.8))
        session.add(CVE(cve_id="CVE-2026-A002", severity="HIGH", cvss_v3_score=7.5))
        session.add(CVE(cve_id="CVE-2026-A003", severity="MEDIUM", cvss_v3_score=5.0, is_in_cisa_kev=True))
        session.commit()
        session.close()

    def test_list_cves(self):
        self._seed_cves()
        resp = client.get("/api/v1/cves")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_filter_cves_by_severity(self):
        self._seed_cves()
        resp = client.get("/api/v1/cves?severity=CRITICAL")
        assert resp.status_code == 200
        for c in resp.json():
            assert c["severity"] == "CRITICAL"

    def test_filter_kev_only(self):
        self._seed_cves()
        resp = client.get("/api/v1/cves?kev_only=true")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["cve_id"] == "CVE-2026-A003"
