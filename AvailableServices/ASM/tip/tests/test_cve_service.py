"""
Unit tests for the CVE Database Service.
"""
import pytest
from datetime import datetime, timezone

from tip.core.models import CVE
from tip.modules.vuln_intel.cve_service import CVEService


class TestCVEIngestion:
    """Test CVE insert / update logic."""

    def test_ingest_new_cve(self, db_session):
        svc = CVEService(db_session)
        parsed = {
            "cve_id": "CVE-2026-9001",
            "description": "Test vulnerability",
            "cvss_v3_score": 7.5,
            "cvss_v3_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H",
            "severity": "HIGH",
            "affected_cpe": ["cpe:2.3:a:*:testpkg:*:*:*:*:*:*:*:*"],
            "has_exploit": False,
        }
        cve = svc.ingest_cve(parsed)
        db_session.flush()
        assert cve.id is not None
        assert cve.cve_id == "CVE-2026-9001"
        assert cve.severity == "HIGH"

    def test_ingest_updates_existing(self, db_session):
        svc = CVEService(db_session)
        parsed1 = {
            "cve_id": "CVE-2026-9002",
            "description": "Initial description",
            "cvss_v3_score": 5.0,
            "severity": "MEDIUM",
        }
        cve1 = svc.ingest_cve(parsed1)
        db_session.flush()

        parsed2 = {
            "cve_id": "CVE-2026-9002",
            "description": "Updated description",
            "cvss_v3_score": 7.5,
            "severity": "HIGH",
        }
        cve2 = svc.ingest_cve(parsed2)
        assert cve2.id == cve1.id
        assert cve2.description == "Updated description"
        assert cve2.severity == "HIGH"

    def test_ingest_requires_cve_id(self, db_session):
        svc = CVEService(db_session)
        with pytest.raises(ValueError):
            svc.ingest_cve({"description": "no ID"})

    def test_ingest_batch(self, db_session):
        svc = CVEService(db_session)
        batch = [
            {"cve_id": "CVE-2026-B001", "severity": "HIGH", "cvss_v3_score": 8.0},
            {"cve_id": "CVE-2026-B002", "severity": "LOW", "cvss_v3_score": 3.1},
            {"cve_id": "CVE-2026-B003", "severity": "CRITICAL", "cvss_v3_score": 9.9},
        ]
        svc.ingest_batch(batch)
        all_cves = db_session.query(CVE).all()
        assert len(all_cves) == 3


class TestCVEQueries:
    """Test CVE query methods."""

    def _seed(self, db_session):
        """Insert test CVEs."""
        svc = CVEService(db_session)
        svc.ingest_cve({"cve_id": "CVE-2026-Q001", "severity": "CRITICAL", "cvss_v3_score": 9.8})
        svc.ingest_cve({"cve_id": "CVE-2026-Q002", "severity": "HIGH", "cvss_v3_score": 7.5})
        svc.ingest_cve({"cve_id": "CVE-2026-Q003", "severity": "MEDIUM", "cvss_v3_score": 5.0})
        svc.ingest_cve({"cve_id": "CVE-2026-Q004", "severity": "CRITICAL", "cvss_v3_score": 10.0, "has_exploit": True})
        db_session.commit()
        # Mark one as KEV
        kev_cve = db_session.query(CVE).filter(CVE.cve_id == "CVE-2026-Q004").first()
        kev_cve.is_in_cisa_kev = True
        db_session.commit()
        return svc

    def test_get_cve_by_id(self, db_session):
        svc = self._seed(db_session)
        cve = svc.get_cve("CVE-2026-Q001")
        assert cve is not None
        assert cve.severity == "CRITICAL"

    def test_get_cve_not_found(self, db_session):
        svc = CVEService(db_session)
        assert svc.get_cve("CVE-NONEXIST") is None

    def test_get_cves_by_severity(self, db_session):
        svc = self._seed(db_session)
        critical = svc.get_cves_by_severity("CRITICAL")
        assert len(critical) == 2

    def test_get_critical_and_high(self, db_session):
        svc = self._seed(db_session)
        results = svc.get_critical_and_high()
        assert len(results) == 3  # 2 CRITICAL + 1 HIGH
        # Should be sorted by score desc
        assert results[0].cvss_v3_score >= results[-1].cvss_v3_score

    def test_get_kev_cves(self, db_session):
        svc = self._seed(db_session)
        kev = svc.get_kev_cves()
        assert len(kev) == 1
        assert kev[0].cve_id == "CVE-2026-Q004"

    def test_get_recent_cves(self, db_session):
        svc = self._seed(db_session)
        recent = svc.get_recent_cves(days=1)
        # All were just inserted
        assert len(recent) == 4
