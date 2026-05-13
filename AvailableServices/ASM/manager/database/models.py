"""
Database models for PostgreSQL/TimescaleDB
SQLAlchemy ORM models
"""

from sqlalchemy import (
    Column, String, Boolean, Integer, DateTime, Text, JSON,
    ForeignKey, Enum as SQLEnum, Table
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from datetime import datetime

Base = declarative_base()


# ==================== ENUMS ====================

class TargetTypeEnum(str, enum.Enum):
    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    IP_ADDRESS = "ip_address"
    CIDR_RANGE = "cidr_range"
    ASN = "asn"
    TLS_CERT = "tls_cert"


class ReconModeEnum(str, enum.Enum):
    PASSIVE = "passive"
    ACTIVE = "active"


class JobStatusEnum(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


# ==================== MODELS ====================

class Scope(Base):
    """Scope table - primary isolation boundary"""
    __tablename__ = "scopes"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Configuration stored as JSON
    config = Column(JSON, nullable=False, default={})
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    created_by = Column(String(255), nullable=True)
    
    # Relationships
    targets = relationship("Target", back_populates="scope", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="scope", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="scope", cascade="all, delete-orphan")


class Target(Base):
    """Targets within a scope"""
    __tablename__ = "targets"
    
    id = Column(String(36), primary_key=True)
    scope_id = Column(String(36), ForeignKey("scopes.id"), nullable=False, index=True)
    type = Column(SQLEnum(TargetTypeEnum), nullable=False)
    value = Column(String(500), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    
    # Relationships
    scope = relationship("Scope", back_populates="targets")


class Schedule(Base):
    """Job schedules"""
    __tablename__ = "schedules"
    
    id = Column(String(36), primary_key=True)
    scope_id = Column(String(36), ForeignKey("scopes.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    mode = Column(SQLEnum(ReconModeEnum), nullable=False)
    cron_expression = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    last_run = Column(DateTime(timezone=True), nullable=True)
    next_run = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    scope = relationship("Scope", back_populates="schedules")
    jobs = relationship("Job", back_populates="schedule")


class Job(Base):
    """Recon jobs - metadata only"""
    __tablename__ = "jobs"
    
    id = Column(String(36), primary_key=True)
    scope_id = Column(String(36), ForeignKey("scopes.id"), nullable=False, index=True)
    schedule_id = Column(String(36), ForeignKey("schedules.id"), nullable=True, index=True)
    
    mode = Column(SQLEnum(ReconModeEnum), nullable=False)
    status = Column(SQLEnum(JobStatusEnum), default=JobStatusEnum.PENDING, nullable=False, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    
    triggered_by = Column(String(50), nullable=False)  # "schedule", "manual", "api"
    
    # Execution times
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Result metadata
    targets_scanned = Column(Integer, default=0)
    findings_count = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    
    # Store config snapshot used for this job
    config_snapshot = Column(JSON, nullable=True)
    
    # Relationships
    scope = relationship("Scope", back_populates="jobs")
    schedule = relationship("Schedule", back_populates="jobs")


class DataSource(Base):
    """External data sources"""
    __tablename__ = "data_sources"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    source_type = Column(String(50), nullable=False)  # "osint", "api", "passive"
    requires_api_key = Column(Boolean, default=False)
    global_enabled = Column(Boolean, default=True, nullable=False)
    
    # Per-scope overrides stored as JSON: {scope_id: enabled}
    scope_overrides = Column(JSON, nullable=True, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    
    # Relationships
    api_keys = relationship("APIKey", back_populates="source", cascade="all, delete-orphan")


class APIKey(Base):
    """API keys for external sources"""
    __tablename__ = "api_keys"
    
    id = Column(String(36), primary_key=True)
    source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    scope_id = Column(String(36), ForeignKey("scopes.id"), nullable=True, index=True)  # None = global
    
    key_value_encrypted = Column(Text, nullable=False)  # Encrypted
    enabled = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    source = relationship("DataSource", back_populates="api_keys")


# ==================== TIME-SERIES TABLES ====================
# These will be converted to TimescaleDB hypertables

class ReconFinding(Base):
    """Time-series table for recon findings (actual scan results)"""
    __tablename__ = "recon_findings"
    
    id = Column(String(36), primary_key=True)
    time = Column(DateTime(timezone=True), nullable=False, index=True)  # TimescaleDB partition key
    
    scope_id = Column(String(36), ForeignKey("scopes.id"), nullable=False, index=True)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    
    # Finding details
    finding_type = Column(String(50), nullable=False)  # "subdomain", "ip", "certificate", "port"
    value = Column(Text, nullable=False)
    source = Column(String(100), nullable=False)  # Which tool/source found it
    
    # Additional data as JSON
    extra_data = Column(JSON, nullable=True)
    
    # Tracking
    first_seen = Column(DateTime(timezone=True), nullable=False)
    last_seen = Column(DateTime(timezone=True), nullable=False)


class DNSRecord(Base):
    """Time-series table for DNS records"""
    __tablename__ = "dns_records"
    
    id = Column(String(36), primary_key=True)
    time = Column(DateTime(timezone=True), nullable=False, index=True)
    
    scope_id = Column(String(36), ForeignKey("scopes.id"), nullable=False, index=True)
    domain = Column(String(500), nullable=False, index=True)
    record_type = Column(String(10), nullable=False)  # A, AAAA, CNAME, MX, etc.
    value = Column(Text, nullable=False)
    ttl = Column(Integer, nullable=True)
    
    first_seen = Column(DateTime(timezone=True), nullable=False)
    last_seen = Column(DateTime(timezone=True), nullable=False)


# ==================== HELPER FUNCTION ====================

def create_hypertables(engine):
    """Convert time-series tables to TimescaleDB hypertables"""
    with engine.connect() as conn:
        # Enable TimescaleDB extension
        conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
        
        # Create hypertables
        conn.execute(
            "SELECT create_hypertable('recon_findings', 'time', "
            "if_not_exists => TRUE, migrate_data => TRUE);"
        )
        conn.execute(
            "SELECT create_hypertable('dns_records', 'time', "
            "if_not_exists => TRUE, migrate_data => TRUE);"
        )
        conn.commit()
