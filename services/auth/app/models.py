import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from tip_db import build_metadata

SCHEMA = "auth"
METADATA = build_metadata(SCHEMA)


class Base(DeclarativeBase):
    metadata = METADATA


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)
    permissions: Mapped[list] = mapped_column(ARRAY(sa.Text), nullable=False, server_default="{}")
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())

    users: Mapped[list["User"]] = relationship(back_populates="role")
    service_accounts: Mapped[list["ServiceAccount"]] = relationship(back_populates="role")


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.roles.id"), nullable=False)
    supplementary_permissions: Mapped[list] = mapped_column(ARRAY(sa.Text), nullable=False, server_default="{}")
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default="true")
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    last_login_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    role: Mapped["Role"] = relationship(back_populates="users")
    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class ServiceAccount(Base):
    __tablename__ = "service_accounts"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.roles.id"), nullable=False)
    supplementary_permissions: Mapped[list] = mapped_column(ARRAY(sa.Text), nullable=False, server_default="{}")
    bootstrap_token_hash: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())

    role: Mapped["Role"] = relationship(back_populates="service_accounts")


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True)
    issued_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    expires_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default="false")
    user_agent: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    action: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    target: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
