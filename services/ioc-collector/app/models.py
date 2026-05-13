import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tip_db import build_metadata
from tip_source_health import build_source_health_table

METADATA = build_metadata("ioc")


class Base(DeclarativeBase):
    metadata = METADATA


class Indicator(Base):
    __tablename__ = "indicators"
    __table_args__ = (UniqueConstraint("type", "normalized_value", name="uq_ioc_indicators_type_value"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(2048), nullable=False)
    raw_value: Mapped[str] = mapped_column(String(2048), nullable=False)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    confidence_score: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.5)
    confidence_inputs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class IndicatorSource(Base):
    __tablename__ = "indicator_sources"

    indicator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ioc.indicators.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    malware_family: Mapped[str | None] = mapped_column(String(255), nullable=True)
    threat_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


SourceHealth = build_source_health_table(METADATA)
