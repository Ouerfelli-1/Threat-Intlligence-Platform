"""initial threat schema"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS threat")

    op.create_table(
        "threats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("severity", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("details", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("confidence_score", sa.Numeric(3, 2), nullable=False, server_default="0.50"),
        sa.Column("confidence_inputs", postgresql.JSONB, nullable=False, server_default="{}"),
        schema="threat",
    )
    op.create_index("ix_threat_threats_observed_at", "threats", ["observed_at"], schema="threat")
    op.create_index("ix_threat_threats_type", "threats", ["type"], schema="threat")
    op.create_index("ix_threat_threats_severity", "threats", ["severity"], schema="threat")

    op.create_table(
        "hibp_breaches",
        sa.Column("name", sa.String(256), primary_key=True),
        sa.Column("breach_date", sa.Date, nullable=True),
        sa.Column("added_date", sa.Date, nullable=True),
        sa.Column("pwn_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("data_classes", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_sensitive", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("raw", postgresql.JSONB, nullable=False, server_default="{}"),
        schema="threat",
    )

    op.create_table(
        "threat_insights",
        sa.Column("threat_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["threat_id"], ["threat.threats.id"], ondelete="CASCADE",
            name="fk_threat_insights_threat_id",
        ),
        schema="threat",
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
        schema="threat",
    )


def downgrade() -> None:
    op.drop_table("source_health", schema="threat")
    op.drop_table("threat_insights", schema="threat")
    op.drop_table("hibp_breaches", schema="threat")
    op.drop_table("threats", schema="threat")
