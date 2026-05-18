"""profile_change_log table for tracking auto-add provenance"""
import sqlalchemy as sa
from alembic import op

revision = "0002_profile_change_log"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profile_change_log",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("change_type", sa.String(64), nullable=False),
        sa.Column("source_resource_type", sa.String(64), nullable=True),
        sa.Column("source_resource_id", sa.String(128), nullable=True),
        sa.Column("added_value", sa.String(512), nullable=True),
        sa.Column("added_by_analyst", sa.String(128), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="cmdb",
    )


def downgrade() -> None:
    op.drop_table("profile_change_log", schema="cmdb")
