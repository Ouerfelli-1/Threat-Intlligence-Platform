import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tip_db import build_metadata

SCHEMA = "flowviz"
METADATA = build_metadata(SCHEMA)


class Base(DeclarativeBase):
    metadata = METADATA


class Flow(Base):
    __tablename__ = "flows"
    __table_args__ = (
        sa.UniqueConstraint("input_hash", name="uq_flowviz_flows_input_hash"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    input_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    input_text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    output: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    generated_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


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
