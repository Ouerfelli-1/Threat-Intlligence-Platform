import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tip_db import build_metadata

SCHEMA = "asm"
METADATA = build_metadata(SCHEMA)


class Base(DeclarativeBase):
    metadata = METADATA


class Scope(Base):
    __tablename__ = "scopes"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default="true")
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


class Target(Base):
    __tablename__ = "targets"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["scope_id"], ["asm.scopes.id"], ondelete="CASCADE",
            name="fk_asm_targets_scope_id",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    type: Mapped[str] = mapped_column(sa.String(32), nullable=False)  # domain|subdomain|ip|cidr|asn|tls_cert
    value: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # Per-target pause toggle. Inactive targets stay in the DB (so removing the
    # pause restores history) but the scanner skips them. Default true means
    # existing rows continue to be scanned without a backfill.
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default="true")
    added_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        # CASCADE on delete: scope removal triggers job removal, which
        # cascades into findings via Finding.job_id. See migration 0002.
        sa.ForeignKeyConstraint(
            ["scope_id"], ["asm.scopes.id"], ondelete="CASCADE",
            name="fk_asm_jobs_scope_id",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="pending")
    started_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    completed_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    findings_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["job_id"], ["asm.jobs.id"], ondelete="CASCADE",
            name="fk_asm_findings_job_id",
        ),
        sa.ForeignKeyConstraint(
            ["target_id"], ["asm.targets.id"], ondelete="SET NULL",
            name="fk_asm_findings_target_id",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    type: Mapped[str] = mapped_column(sa.String(64), nullable=False)  # subdomain|ip|cert|open_port
    value: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    source: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    discovered_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


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
