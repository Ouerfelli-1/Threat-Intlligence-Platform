import uuid
from decimal import Decimal
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, NUMERIC, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tip_db import build_metadata

SCHEMA = "indicator"
METADATA = build_metadata(SCHEMA)


class Base(DeclarativeBase):
    metadata = METADATA


class Investigation(Base):
    __tablename__ = "investigations"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    indicator_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    normalized_value: Mapped[str] = mapped_column(sa.Text, nullable=False)
    raw_value: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="pending")
    verdict: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    confidence: Mapped[Optional[Decimal]] = mapped_column(NUMERIC(3, 2), nullable=True)
    risk_score: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    model_name: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    investigated_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    duration_ms: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)


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
