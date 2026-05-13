"""
SQLAlchemy ORM models for the Threat Intelligence Platform.

Tables:
  - organizations      : Companies / targets being monitored
  - assets             : Discovered assets (domains, IPs, services)
  - software           : Software inventory (synced from Wazuh Syscollector)
  - asset_software     : M2M link between assets and software
  - cves               : CVE / vulnerability records
  - asset_cve          : M2M link between assets and CVEs
  - data_leaks         : Data-leak intelligence records
  - alerts             : Unified alerts from all modules
  - wazuh_events       : Raw IDS events ingested from Wazuh
  - correlation_results: Outputs of cross-module correlation rules
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from tip.core.database import Base


# ── helpers ──────────────────────────────────────────────────────
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Association tables ───────────────────────────────────────────

asset_software = Table(
    "asset_software",
    Base.metadata,
    Column("asset_id", Integer, ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
    Column("software_id", Integer, ForeignKey("software.id", ondelete="CASCADE"), primary_key=True),
)

asset_cve = Table(
    "asset_cve",
    Base.metadata,
    Column("asset_id", Integer, ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
    Column("cve_id", Integer, ForeignKey("cves.id", ondelete="CASCADE"), primary_key=True),
    Column("detected_at", DateTime, default=_utcnow),
)


# ── Organization ─────────────────────────────────────────────────

class Organization(Base):
    """A company / scope that is being monitored."""
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    primary_domain = Column(String(255), nullable=False, unique=True)
    # Loose reference to the existing recon scope (UUID string from recon DB)
    recon_scope_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # relationships
    assets = relationship("Asset", back_populates="organization", cascade="all, delete-orphan")
    leaks = relationship("DataLeak", back_populates="organization", cascade="all, delete-orphan")


# ── Asset ────────────────────────────────────────────────────────

class Asset(Base):
    """An asset discovered by the ASM module (domain, IP, service)."""
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)

    # identification
    asset_type = Column(String(50), nullable=False)  # domain | subdomain | ip | service
    hostname = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)
    port = Column(Integer, nullable=True)

    # discovery metadata
    discovery_source = Column(String(100), nullable=True)
    first_seen = Column(DateTime, default=_utcnow)
    last_seen = Column(DateTime, default=_utcnow)
    is_active = Column(Boolean, default=True)

    # technical details (stored as JSON)
    technologies = Column(JSON, nullable=True)
    ssl_info = Column(JSON, nullable=True)
    headers = Column(JSON, nullable=True)
    extra_data = Column(JSON, nullable=True)

    # risk scoring
    risk_score = Column(Float, default=0.0)
    risk_factors = Column(JSON, nullable=True)

    # Wazuh agent mapping (set manually or via IP match)
    wazuh_agent_id = Column(String(50), nullable=True)

    # relationships
    organization = relationship("Organization", back_populates="assets")
    software = relationship("Software", secondary=asset_software, back_populates="assets")
    vulnerabilities = relationship("CVE", secondary=asset_cve, back_populates="affected_assets")
    alerts = relationship("Alert", back_populates="asset", cascade="all, delete-orphan")


# ── Software ─────────────────────────────────────────────────────

class Software(Base):
    """Software package from Wazuh Syscollector inventory."""
    __tablename__ = "software"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    vendor = Column(String(255), nullable=True)
    version = Column(String(100), nullable=True)
    cpe = Column(String(500), nullable=True)  # Common Platform Enumeration 2.3
    architecture = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    # relationships
    assets = relationship("Asset", secondary=asset_software, back_populates="software")


# ── CVE ──────────────────────────────────────────────────────────

class CVE(Base):
    """A CVE / vulnerability record."""
    __tablename__ = "cves"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cve_id = Column(String(20), unique=True, nullable=False, index=True)  # e.g. CVE-2024-12345

    description = Column(Text, nullable=True)
    cvss_v3_score = Column(Float, nullable=True)
    cvss_v3_vector = Column(String(100), nullable=True)
    severity = Column(String(20), nullable=True)  # CRITICAL | HIGH | MEDIUM | LOW

    # affected products (CPE patterns as JSON list)
    affected_cpe = Column(JSON, nullable=True)
    affected_products = Column(JSON, nullable=True)

    # exploit information
    has_exploit = Column(Boolean, default=False)
    exploit_references = Column(JSON, nullable=True)
    is_in_cisa_kev = Column(Boolean, default=False)

    # dates
    published_date = Column(DateTime, nullable=True)
    last_modified = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    # relationships
    affected_assets = relationship("Asset", secondary=asset_cve, back_populates="vulnerabilities")


# ── Data Leak ────────────────────────────────────────────────────

class DataLeak(Base):
    """A data-leak record from the leak-detection module."""
    __tablename__ = "data_leaks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)

    leak_source = Column(String(255), nullable=True)
    leak_type = Column(String(50), nullable=True)  # credentials | database_dump | documents
    leak_date = Column(DateTime, nullable=True)
    discovered_date = Column(DateTime, default=_utcnow)

    affected_emails = Column(JSON, nullable=True)
    affected_domains = Column(JSON, nullable=True)
    record_count = Column(Integer, default=0)
    sample_data = Column(JSON, nullable=True)

    severity = Column(String(20), nullable=True)
    contains_passwords = Column(Boolean, default=False)
    contains_pii = Column(Boolean, default=False)
    status = Column(String(50), default="new")  # new | investigating | resolved

    # relationships
    organization = relationship("Organization", back_populates="leaks")
    alerts = relationship("Alert", back_populates="leak", cascade="all, delete-orphan")


# ── Alert ────────────────────────────────────────────────────────

class Alert(Base):
    """Unified alert from any module or the correlation engine."""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)

    source_module = Column(String(50), nullable=False)  # asm | vuln_intel | data_leak | ids | correlation
    alert_type = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False)        # CRITICAL | HIGH | MEDIUM | LOW | INFO
    priority = Column(Integer, default=5)

    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    raw_data = Column(JSON, nullable=True)

    # optional FK references
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    cve_id = Column(Integer, ForeignKey("cves.id", ondelete="SET NULL"), nullable=True)
    leak_id = Column(Integer, ForeignKey("data_leaks.id", ondelete="SET NULL"), nullable=True)

    # workflow
    status = Column(String(50), default="open")  # open | acknowledged | resolved | false_positive
    assigned_to = Column(String(255), nullable=True)

    # external sync IDs
    misp_event_id = Column(String(50), nullable=True)
    opencti_report_id = Column(String(50), nullable=True)

    # timestamps
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    resolved_at = Column(DateTime, nullable=True)

    # relationships
    asset = relationship("Asset", back_populates="alerts")
    leak = relationship("DataLeak", back_populates="alerts")


# ── Wazuh Event ──────────────────────────────────────────────────

class WazuhEvent(Base):
    """Raw IDS event ingested from Wazuh."""
    __tablename__ = "wazuh_events"

    id = Column(Integer, primary_key=True, autoincrement=True)

    wazuh_id = Column(String(100), nullable=True, unique=True)
    rule_id = Column(Integer, nullable=True)
    rule_level = Column(Integer, nullable=True)
    rule_description = Column(String(500), nullable=True)

    agent_id = Column(String(50), nullable=True)
    agent_name = Column(String(255), nullable=True)
    source_ip = Column(String(45), nullable=True)

    full_log = Column(Text, nullable=True)
    decoded_data = Column(JSON, nullable=True)

    timestamp = Column(DateTime, nullable=True)
    ingested_at = Column(DateTime, default=_utcnow)


# ── Correlation Result ───────────────────────────────────────────

class CorrelationResult(Base):
    """Persisted output of a correlation-engine run."""
    __tablename__ = "correlation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    rule_name = Column(String(100), nullable=False)
    risk_score = Column(Float, default=0.0)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
