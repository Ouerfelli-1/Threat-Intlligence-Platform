"""analyst_status + notes table + insight override for CVEs"""
import sqlalchemy as sa
from alembic import op

revision = "0002_analyst_layer"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cves",
        sa.Column("analyst_status", sa.String(32), nullable=False, server_default="unreviewed"),
        schema="vuln",
    )
    op.create_index("ix_vuln_cves_analyst_status", "cves", ["analyst_status"], schema="vuln")

    op.add_column(
        "cve_insights",
        sa.Column("analyst_override", sa.dialects.postgresql.JSONB, nullable=True),
        schema="vuln",
    )

    op.create_table(
        "cve_notes",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cve_id", sa.String(20), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("pinned", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("author", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="vuln",
    )
    op.create_index("ix_vuln_cve_notes_cve_id_pinned", "cve_notes", ["cve_id", "pinned"], schema="vuln")


def downgrade() -> None:
    op.drop_table("cve_notes", schema="vuln")
    op.drop_column("cve_insights", "analyst_override", schema="vuln")
    op.drop_index("ix_vuln_cves_analyst_status", table_name="cves", schema="vuln")
    op.drop_column("cves", "analyst_status", schema="vuln")
