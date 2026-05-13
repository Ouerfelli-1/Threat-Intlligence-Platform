from datetime import datetime, date

from sqlalchemy import Boolean, Date, DateTime, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tip_db import build_metadata
from tip_source_health import build_source_health_table

METADATA = build_metadata("vuln")


class Base(DeclarativeBase):
    metadata = METADATA


class CVE(Base):
    __tablename__ = "cves"

    cve_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cvss_v3_score: Mapped[float | None] = mapped_column(Numeric(3, 1), nullable=True)
    cvss_v3_vector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    cwe: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    affected_products: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    references: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EPSS(Base):
    __tablename__ = "epss"

    cve_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    epss: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    percentile: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class KEV(Base):
    __tablename__ = "kev"

    cve_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_added: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ransomware_use: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class CVEInsight(Base):
    __tablename__ = "cve_insights"

    cve_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


SourceHealth = build_source_health_table(METADATA)
