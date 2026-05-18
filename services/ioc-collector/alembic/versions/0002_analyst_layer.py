"""analyst_status + notes table for indicators"""
import sqlalchemy as sa
from alembic import op

revision = "0002_analyst_layer"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "indicators",
        sa.Column("analyst_status", sa.String(32), nullable=False, server_default="unreviewed"),
        schema="ioc",
    )
    op.create_index("ix_ioc_indicators_analyst_status", "indicators", ["analyst_status"], schema="ioc")

    op.create_table(
        "indicator_notes",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("indicator_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("pinned", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("author", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="ioc",
    )
    op.create_index("ix_ioc_indicator_notes_indicator_id_pinned", "indicator_notes", ["indicator_id", "pinned"], schema="ioc")


def downgrade() -> None:
    op.drop_table("indicator_notes", schema="ioc")
    op.drop_index("ix_ioc_indicators_analyst_status", table_name="indicators", schema="ioc")
    op.drop_column("indicators", "analyst_status", schema="ioc")
