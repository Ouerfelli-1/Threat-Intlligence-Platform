import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tip_db import build_metadata

SCHEMA = "actors"
METADATA = build_metadata(SCHEMA)


class Base(DeclarativeBase):
    metadata = METADATA


class Actor(Base):
    __tablename__ = "actors"
    __table_args__ = (
        sa.UniqueConstraint("mitre_id", name="uq_actors_mitre_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mitre_id: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    name: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    aliases: Mapped[list] = mapped_column(ARRAY(sa.String), nullable=False, server_default="{}")
    origin_country: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    motivation: Mapped[list] = mapped_column(ARRAY(sa.String), nullable=False, server_default="{}")
    active_since: Mapped[sa.Date | None] = mapped_column(sa.Date, nullable=True)
    last_seen: Mapped[sa.Date | None] = mapped_column(sa.Date, nullable=True)
    target_sectors: Mapped[list] = mapped_column(ARRAY(sa.String), nullable=False, server_default="{}")
    target_countries: Mapped[list] = mapped_column(ARRAY(sa.String), nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="active")
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class ActorTTP(Base):
    __tablename__ = "actor_ttps"
    __table_args__ = (
        sa.PrimaryKeyConstraint("actor_id", "technique_id", name="pk_actors_actor_ttps"),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["actors.actors.id"], ondelete="CASCADE",
            name="fk_actors_actor_ttps_actor_id",
        ),
        {"schema": SCHEMA},
    )

    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    technique_id: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    technique_name: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    sub_technique_id: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    confidence: Mapped[float] = mapped_column(sa.Numeric(3, 2), nullable=False, server_default="0.50")
    source: Mapped[str] = mapped_column(sa.String(128), nullable=False, server_default="mitre")


class Tool(Base):
    __tablename__ = "tools"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    aliases: Mapped[list] = mapped_column(ARRAY(sa.String), nullable=False, server_default="{}")
    type: Mapped[str] = mapped_column(sa.String(64), nullable=False)  # malware | tool
    mitre_id: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class ActorTool(Base):
    __tablename__ = "actor_tools"
    __table_args__ = (
        sa.PrimaryKeyConstraint("actor_id", "tool_id", name="pk_actors_actor_tools"),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["actors.actors.id"], ondelete="CASCADE",
            name="fk_actors_actor_tools_actor_id",
        ),
        sa.ForeignKeyConstraint(
            ["tool_id"], ["actors.tools.id"], ondelete="CASCADE",
            name="fk_actors_actor_tools_tool_id",
        ),
        {"schema": SCHEMA},
    )

    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tool_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class RansomwareGroup(Base):
    __tablename__ = "ransomware_groups"
    __table_args__ = (
        sa.UniqueConstraint("name", name="uq_actors_ransomware_groups_name"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    aliases: Mapped[list] = mapped_column(ARRAY(sa.String), nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="active")
    first_seen: Mapped[sa.Date | None] = mapped_column(sa.Date, nullable=True)
    last_seen: Mapped[sa.Date | None] = mapped_column(sa.Date, nullable=True)
    variants: Mapped[list] = mapped_column(ARRAY(sa.String), nullable=False, server_default="{}")
    leak_site_url: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    ransom_range: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class RansomwareVictim(Base):
    __tablename__ = "ransomware_victims"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["group_id"], ["actors.ransomware_groups.id"], ondelete="CASCADE",
            name="fk_actors_ransomware_victims_group_id",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    victim_name: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    sector: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    country: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    disclosed_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(sa.String(128), nullable=False, server_default="ransomware.live")
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # sha256(group_id || '|' || victim_name || '|' || disclosed_at_iso) — UNIQUE
    dedup_key: Mapped[str] = mapped_column(sa.String(64), nullable=False, server_default="")


class ActorInsight(Base):
    __tablename__ = "actor_insights"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["actor_id"], ["actors.actors.id"], ondelete="CASCADE",
            name="fk_actors_actor_insights_actor_id",
        ),
        {"schema": SCHEMA},
    )

    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
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
