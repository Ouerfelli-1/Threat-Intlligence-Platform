"""analyst_status + manual_source + notes table + insight override for threats"""
import sqlalchemy as sa
from alembic import op

revision = "0002_analyst_layer"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "threats",
        sa.Column("analyst_status", sa.String(32), nullable=False, server_default="unreviewed"),
        schema="threat",
    )
    op.add_column(
        "threats",
        sa.Column("manual_source", sa.String(128), nullable=True),
        schema="threat",
    )
    op.create_index("ix_threat_threats_analyst_status", "threats", ["analyst_status"], schema="threat")

    op.add_column(
        "threat_insights",
        sa.Column("analyst_override", sa.dialects.postgresql.JSONB, nullable=True),
        schema="threat",
    )

    op.create_table(
        "threat_notes",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("threat_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("pinned", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("author", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="threat",
    )
    op.create_index("ix_threat_threat_notes_threat_id_pinned", "threat_notes", ["threat_id", "pinned"], schema="threat")


def downgrade() -> None:
    op.drop_table("threat_notes", schema="threat")
    op.drop_column("threat_insights", "analyst_override", schema="threat")
    op.drop_index("ix_threat_threats_analyst_status", table_name="threats", schema="threat")
    op.drop_column("threats", "manual_source", schema="threat")
    op.drop_column("threats", "analyst_status", schema="threat")
