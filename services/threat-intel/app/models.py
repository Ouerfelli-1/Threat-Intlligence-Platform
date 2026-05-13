import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tip_db import build_metadata

SCHEMA = "threat"
METADATA = build_metadata(SCHEMA)


class Base(DeclarativeBase):
    metadata = METADATA


class Threat(Base):
    __tablename__ = "threats"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    source: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    source_url: Mapped[str | None] = mapped_column(sa.String(2048), nullable=True)
    observed_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    summary: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    severity: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="medium")
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    confidence_score: Mapped[float] = mapped_column(sa.Numeric(3, 2), nullable=False, server_default="0.50")
    confidence_inputs: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class HIBPBreach(Base):
    __tablename__ = "hibp_breaches"
    __table_args__ = {"schema": SCHEMA}

    name: Mapped[str] = mapped_column(sa.String(256), primary_key=True)
    breach_date: Mapped[sa.Date | None] = mapped_column(sa.Date, nullable=True)
    added_date: Mapped[sa.Date | None] = mapped_column(sa.Date, nullable=True)
    pwn_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    data_classes: Mapped[list] = mapped_column(sa.dialects.postgresql.ARRAY(sa.String), nullable=False, server_default="{}")
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    is_verified: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default="false")
    is_sensitive: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default="false")
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class ThreatInsight(Base):
    __tablename__ = "threat_insights"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["threat_id"], ["threat.threats.id"], ondelete="CASCADE",
            name="fk_threat_insights_threat_id",
        ),
        {"schema": SCHEMA},
    )

    threat_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    generated_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


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
