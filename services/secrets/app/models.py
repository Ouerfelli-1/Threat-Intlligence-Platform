import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tip_db import build_metadata

SCHEMA = "secrets"
METADATA = build_metadata(SCHEMA)


class Base(DeclarativeBase):
    metadata = METADATA


class Secret(Base):
    __tablename__ = "secrets"
    __table_args__ = {"schema": SCHEMA}

    name: Mapped[str] = mapped_column(sa.String(256), primary_key=True)
    value_encrypted: Mapped[bytes] = mapped_column(sa.LargeBinary, nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    updated_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


class AccessLog(Base):
    __tablename__ = "access_log"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    secret_name: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    actor: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    action: Mapped[str] = mapped_column(sa.String(32), nullable=False)  # read|write|rotate|delete
    at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    source_ip: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
