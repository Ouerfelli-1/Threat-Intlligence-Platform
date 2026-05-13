"""initial cmdb schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-12 00:00:00

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS cmdb")

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("hostname", sa.String(255), nullable=False, unique=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("os", sa.String(128), nullable=True),
        sa.Column("software", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("device_type", sa.String(64), nullable=True),
        sa.Column("criticality", sa.String(32), nullable=True),
        sa.Column("owner", sa.String(128), nullable=True),
        sa.Column("location", sa.String(128), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="cmdb",
    )
    op.create_index("ix_cmdb_assets_hostname", "assets", ["hostname"], schema="cmdb")

    op.create_table(
        "org_profile_versions",
        sa.Column("version", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("edited_by", sa.String(128), nullable=True),
        sa.Column("edited_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="cmdb",
    )


def downgrade() -> None:
    op.drop_table("org_profile_versions", schema="cmdb")
    op.drop_index("ix_cmdb_assets_hostname", table_name="assets", schema="cmdb")
    op.drop_table("assets", schema="cmdb")
