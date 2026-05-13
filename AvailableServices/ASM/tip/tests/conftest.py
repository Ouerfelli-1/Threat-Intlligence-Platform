"""
Shared pytest fixtures for TIP unit tests.

Uses an in-memory SQLite database to avoid needing PostgreSQL,
with a fresh schema per test function.
"""
import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# ── Make sure the project root is importable ─────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Patch settings BEFORE any tip module is imported ─────────────
#    Override the DB URL so it uses SQLite in-memory.
os.environ["TIP_DB_HOST"] = "localhost"
os.environ["TIP_DB_PORT"] = "5433"
os.environ["TIP_DB_NAME"] = "test"
os.environ["TIP_DB_USER"] = "test"
os.environ["TIP_DB_PASSWORD"] = "test"
os.environ["WAZUH_API_URL"] = "https://mock-wazuh:55000"
os.environ["MISP_URL"] = "https://mock-misp"
os.environ["MISP_API_KEY"] = "test-misp-key"
os.environ["OPENCTI_URL"] = "http://mock-opencti:8080"
os.environ["OPENCTI_API_KEY"] = "test-opencti-key"
os.environ["LEAK_API_URL"] = "http://mock-leak-api:8081"
os.environ["NVD_API_KEY"] = ""
os.environ["RECON_FINDINGS_API_URL"] = "http://mock-recon:8001"

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from tip.core.database import Base


# ── SQLite in-memory engine shared across a test session ─────────

@pytest.fixture(scope="function")
def db_engine():
    """Create a fresh in-memory SQLite engine per test."""
    engine = create_engine("sqlite:///:memory:", echo=False)

    # SQLite doesn't support JSON natively; let it pass through
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Import models so they register with Base
    import tip.core.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Provide a transactional session that rolls back after each test."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


# ── Convenience fixtures for common test data ────────────────────

@pytest.fixture
def sample_org(db_session):
    """Create and return a sample Organization."""
    from tip.core.models import Organization
    org = Organization(
        name="Example Corp",
        primary_domain="example.com",
        recon_scope_id="scope-uuid-001",
    )
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def sample_asset(db_session, sample_org):
    """Create a sample active web-facing Asset."""
    from tip.core.models import Asset
    asset = Asset(
        organization_id=sample_org.id,
        asset_type="service",
        hostname="www.example.com",
        ip_address="93.184.216.34",
        port=443,
        is_active=True,
        technologies=["nginx", "wordpress"],
        wazuh_agent_id="001",
    )
    db_session.add(asset)
    db_session.flush()
    return asset


@pytest.fixture
def sample_software(db_session, sample_asset):
    """Create sample Software linked to sample_asset."""
    from tip.core.models import Software
    sw = Software(
        name="apache2",
        vendor="ubuntu_developers",
        version="2.4.52-1ubuntu4.6",
        cpe="cpe:2.3:a:ubuntu_developers:apache2:2.4.52-1ubuntu4.6:*:*:*:*:*:*:*",
    )
    db_session.add(sw)
    db_session.flush()
    sample_asset.software.append(sw)
    db_session.flush()
    return sw


@pytest.fixture
def sample_cve(db_session):
    """Create a sample critical CVE that matches apache."""
    from tip.core.models import CVE
    cve = CVE(
        cve_id="CVE-2026-0001",
        description="Critical RCE in Apache HTTP Server",
        cvss_v3_score=9.8,
        cvss_v3_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        severity="CRITICAL",
        affected_cpe=["cpe:2.3:a:*:apache2:*:*:*:*:*:*:*:*"],
        has_exploit=True,
    )
    db_session.add(cve)
    db_session.flush()
    return cve


@pytest.fixture
def sample_leak(db_session, sample_org):
    """Create a sample DataLeak record."""
    from tip.core.models import DataLeak
    from datetime import datetime, timezone
    leak = DataLeak(
        organization_id=sample_org.id,
        leak_source="DarkMarket Forums",
        leak_type="credentials",
        leak_date=datetime(2026, 2, 20, 10, 0, tzinfo=timezone.utc),
        affected_emails=["admin@example.com"],
        affected_domains=["example.com", "www.example.com"],
        record_count=1500,
        severity="HIGH",
        contains_passwords=True,
        contains_pii=False,
        status="new",
    )
    db_session.add(leak)
    db_session.flush()
    return leak
