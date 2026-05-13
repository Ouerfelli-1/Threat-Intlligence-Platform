"""initial ioc schema"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS ioc")

    op.create_table(
        "indicators",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("normalized_value", sa.String(2048), nullable=False),
        sa.Column("raw_value", sa.String(2048), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("confidence_score", sa.Numeric(3, 2), nullable=False, server_default="0.50"),
        sa.Column("confidence_inputs", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.UniqueConstraint("type", "normalized_value", name="uq_ioc_indicators_type_value"),
        schema="ioc",
    )
    op.create_index("ix_ioc_indicators_type_norm", "indicators", ["type", "normalized_value"], schema="ioc")
    op.create_index("ix_ioc_indicators_last_seen", "indicators", ["last_seen"], schema="ioc")

    op.create_table(
        "indicator_sources",
        sa.Column("indicator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_name", sa.String(128), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("first_reported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_reported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("malware_family", sa.String(255), nullable=True),
        sa.Column("threat_type", sa.String(64), nullable=True),
        sa.Column("raw", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.PrimaryKeyConstraint("indicator_id", "source_name", name="pk_ioc_indicator_sources"),
        sa.ForeignKeyConstraint(
            ["indicator_id"], ["ioc.indicators.id"], ondelete="CASCADE",
            name="fk_ioc_indicator_sources_indicator_id_indicators",
        ),
        schema="ioc",
    )

    op.create_table(
        "source_health",
        sa.Column("source_name", sa.String(128), primary_key=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_failures", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("last_error", sa.String(2048), nullable=True),
        sa.Column("last_http_status", sa.Integer, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema="ioc",
    )


def downgrade() -> None:
    op.drop_table("source_health", schema="ioc")
    op.drop_table("indicator_sources", schema="ioc")
    op.drop_table("indicators", schema="ioc")
