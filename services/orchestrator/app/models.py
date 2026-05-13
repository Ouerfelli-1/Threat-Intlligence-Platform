import uuid
from decimal import Decimal
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, NUMERIC, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tip_db import build_metadata

SCHEMA = "orchestrator"
METADATA = build_metadata(SCHEMA)


class Base(DeclarativeBase):
    metadata = METADATA


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    model_name: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    generated_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


class CveRelevance(Base):
    __tablename__ = "cve_relevance"
    __table_args__ = (
        sa.PrimaryKeyConstraint("cve_id", "scored_at"),
        {"schema": SCHEMA},
    )

    cve_id: Mapped[str] = mapped_column(sa.Text, nullable=False)
    relevance_score: Mapped[Decimal] = mapped_column(NUMERIC(3, 2), nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    scored_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


class ActorLikelihood(Base):
    __tablename__ = "actor_likelihood"
    __table_args__ = (
        sa.PrimaryKeyConstraint("actor_id", "scored_at"),
        {"schema": SCHEMA},
    )

    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    likelihood_score: Mapped[Decimal] = mapped_column(NUMERIC(3, 2), nullable=False)
    ttps_overlap: Mapped[list] = mapped_column(ARRAY(sa.Text), nullable=False, server_default="{}")
    rationale: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    scored_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


class Correlation(Base):
    __tablename__ = "correlations"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    detected_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


class SourceHealth(Base):
    __tablename__ = "source_health"
    __table_args__ = {"schema": SCHEMA}

    source_name: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    last_success_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="active")
    last_error: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    last_http_status: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    updated_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
