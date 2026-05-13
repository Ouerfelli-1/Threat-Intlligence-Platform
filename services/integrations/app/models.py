import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tip_db import build_metadata

SCHEMA = "integrations"
METADATA = build_metadata(SCHEMA)


class Base(DeclarativeBase):
    metadata = METADATA


class WazuhAlert(Base):
    __tablename__ = "wazuh_alerts"
    __table_args__ = {"schema": SCHEMA}

    alert_id: Mapped[str] = mapped_column(sa.String(256), primary_key=True)
    agent_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    agent_name: Mapped[str | None] = mapped_column(sa.String(256), nullable=True)
    rule_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    rule_description: Mapped[str | None] = mapped_column(sa.String(1024), nullable=True)
    severity: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    timestamp: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class WazuhAgent(Base):
    __tablename__ = "wazuh_agents"
    __table_args__ = {"schema": SCHEMA}

    agent_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    hostname: Mapped[str | None] = mapped_column(sa.String(256), nullable=True)
    ip: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    os: Mapped[str | None] = mapped_column(sa.String(256), nullable=True)
    version: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    last_seen: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="active")
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class MISPEvent(Base):
    __tablename__ = "misp_events"
    __table_args__ = {"schema": SCHEMA}

    event_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    info: Mapped[str | None] = mapped_column(sa.String(1024), nullable=True)
    threat_level_id: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    analysis: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    date: Mapped[sa.Date | None] = mapped_column(sa.Date, nullable=True)
    org: Mapped[str | None] = mapped_column(sa.String(256), nullable=True)
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class MISPIoc(Base):
    __tablename__ = "misp_iocs"
    __table_args__ = (
        sa.UniqueConstraint("event_id", "type", "normalized_value", name="uq_integrations_misp_iocs"),
        sa.ForeignKeyConstraint(
            ["event_id"], ["integrations.misp_events.event_id"], ondelete="CASCADE",
            name="fk_integrations_misp_iocs_event_id",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    type: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    normalized_value: Mapped[str] = mapped_column(sa.String(2048), nullable=False)
    raw_value: Mapped[str] = mapped_column(sa.String(2048), nullable=False)
    comment: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    to_ids: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default="false")
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class MISPPush(Base):
    __tablename__ = "misp_pushes"
    __table_args__ = {"schema": SCHEMA}

    local_indicator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    misp_event_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    misp_attribute_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    pushed_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


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
