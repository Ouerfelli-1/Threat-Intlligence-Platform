"""initial orchestrator schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, NUMERIC, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "orchestrator"


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("model_name", sa.Text, nullable=True),
        sa.Column("prompt_version", sa.Text, nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )

    op.create_table(
        "cve_relevance",
        sa.Column("cve_id", sa.Text, nullable=False),
        sa.Column("relevance_score", NUMERIC(3, 2), nullable=False),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column(
            "scored_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("cve_id", "scored_at"),
        schema=SCHEMA,
    )

    op.create_table(
        "actor_likelihood",
        sa.Column("actor_id", UUID(as_uuid=True), nullable=False),
        sa.Column("likelihood_score", NUMERIC(3, 2), nullable=False),
        sa.Column("ttps_overlap", sa.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column(
            "scored_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("actor_id", "scored_at"),
        schema=SCHEMA,
    )

    op.create_table(
        "correlations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )

    op.create_table(
        "source_health",
        sa.Column("source_name", sa.Text, primary_key=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_failures", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.Text, nullable=False, server_default="active"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("last_http_status", sa.Integer, nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )

    op.create_index("ix_reports_kind", "reports", ["kind"], schema=SCHEMA)
    op.create_index("ix_reports_generated_at", "reports", ["generated_at"], schema=SCHEMA)
    op.create_index("ix_correlations_detected_at", "correlations", ["detected_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("source_health", schema=SCHEMA)
    op.drop_table("correlations", schema=SCHEMA)
    op.drop_table("actor_likelihood", schema=SCHEMA)
    op.drop_table("cve_relevance", schema=SCHEMA)
    op.drop_table("reports", schema=SCHEMA)
