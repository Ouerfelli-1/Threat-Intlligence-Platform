import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tip_db import build_metadata

SCHEMA = "scheduler"
METADATA = build_metadata(SCHEMA)


class Base(DeclarativeBase):
    metadata = METADATA


class JobRunHistory(Base):
    __tablename__ = "job_run_history"
    __table_args__ = {"schema": SCHEMA}

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    job_id: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    triggered_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    completed_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="running")
    http_status: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
