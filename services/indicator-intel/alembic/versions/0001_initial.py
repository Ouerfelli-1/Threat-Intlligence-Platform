"""initial indicator schema

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

SCHEMA = "indicator"


def upgrade() -> None:
    op.create_table(
        "investigations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("indicator_type", sa.String(32), nullable=False),
        sa.Column("normalized_value", sa.Text, nullable=False),
        sa.Column("raw_value", sa.Text, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("verdict", sa.String(64), nullable=True),
        sa.Column("confidence", NUMERIC(3, 2), nullable=True),
        sa.Column("risk_score", sa.Integer, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("model_name", sa.Text, nullable=True),
        sa.Column(
            "investigated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("duration_ms", sa.Integer, nullable=True),
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

    op.create_index(
        "ix_investigations_type_value",
        "investigations",
        ["indicator_type", "normalized_value"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_investigations_investigated_at",
        "investigations",
        ["investigated_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("source_health", schema=SCHEMA)
    op.drop_table("investigations", schema=SCHEMA)
