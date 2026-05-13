"""initial secrets schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "secrets"


def upgrade() -> None:
    op.create_table(
        "secrets",
        sa.Column("name", sa.String(256), primary_key=True),
        sa.Column("value_encrypted", sa.LargeBinary, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )

    op.create_table(
        "access_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("secret_name", sa.String(256), nullable=False),
        sa.Column("actor", sa.String(256), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column(
            "at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("source_ip", sa.String(64), nullable=True),
        schema=SCHEMA,
    )

    op.create_index(
        "ix_access_log_secret_name",
        "access_log",
        ["secret_name"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_access_log_at",
        "access_log",
        ["at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("access_log", schema=SCHEMA)
    op.drop_table("secrets", schema=SCHEMA)
