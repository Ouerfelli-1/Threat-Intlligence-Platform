import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tip_db import build_metadata

SCHEMA = "domainwatch"
METADATA = build_metadata(SCHEMA)


class Base(DeclarativeBase):
    metadata = METADATA


class Domain(Base):
    __tablename__ = "domains"
    __table_args__ = (
        sa.UniqueConstraint("name", name="uq_domainwatch_domains_name"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default="true")
    added_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    last_checked_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["domain_id"], ["domainwatch.domains.id"], ondelete="CASCADE",
            name="fk_domainwatch_snapshots_domain_id",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    captured_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    content_hash: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(sa.String(1024), nullable=True)


class Change(Base):
    __tablename__ = "changes"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["domain_id"], ["domainwatch.domains.id"], ondelete="CASCADE",
            name="fk_domainwatch_changes_domain_id",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    detected_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    change_type: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    before: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    after: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class DomainIOC(Base):
    __tablename__ = "domain_iocs"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["domain_id"], ["domainwatch.domains.id"], ondelete="CASCADE",
            name="fk_domainwatch_domain_iocs_domain_id",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ioc_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    value: Mapped[str] = mapped_column(sa.String(2048), nullable=False)
    source: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    observed_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


class DomainSubdomain(Base):
    __tablename__ = "domain_subdomains"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["domain_id"], ["domainwatch.domains.id"], ondelete="CASCADE",
            name="fk_domainwatch_domain_subdomains_domain_id",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subdomain: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    source: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    observed_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


class SourceHealth(Base):
    __tablename__ = "source_health"
    __table_args__ = {"schema": SCHEMA}

    source_name: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    last_success_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="active")
    last_error: Mapped[str | None] = mapped_column(sa.String(2048), nullable=True)
    last_http_status: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    updated_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
