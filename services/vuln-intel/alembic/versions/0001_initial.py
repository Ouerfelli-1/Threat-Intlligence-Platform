"""initial vuln schema"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS vuln")

    op.create_table(
        "cves",
        sa.Column("cve_id", sa.String(20), primary_key=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("cvss_v3_score", sa.Numeric(3, 1), nullable=True),
        sa.Column("cvss_v3_vector", sa.String(128), nullable=True),
        sa.Column("severity", sa.String(16), nullable=True),
        sa.Column("cwe", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("affected_products", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("references", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="vuln",
    )
    op.create_index("ix_vuln_cves_severity", "cves", ["severity"], schema="vuln")
    op.create_index("ix_vuln_cves_last_modified_at", "cves", ["last_modified_at"], schema="vuln")

    op.create_table(
        "epss",
        sa.Column("cve_id", sa.String(20), primary_key=True),
        sa.Column("epss", sa.Numeric(5, 4), nullable=False),
        sa.Column("percentile", sa.Numeric(5, 4), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False),
        schema="vuln",
    )

    op.create_table(
        "kev",
        sa.Column("cve_id", sa.String(20), primary_key=True),
        sa.Column("vendor", sa.String(255), nullable=True),
        sa.Column("product", sa.String(255), nullable=True),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column("date_added", sa.Date, nullable=True),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("ransomware_use", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text, nullable=True),
        schema="vuln",
    )

    op.create_table(
        "cve_insights",
        sa.Column("cve_id", sa.String(20), primary_key=True),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("model_name", sa.String(128), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="vuln",
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
        schema="vuln",
    )


def downgrade() -> None:
    op.drop_table("source_health", schema="vuln")
    op.drop_table("cve_insights", schema="vuln")
    op.drop_table("kev", schema="vuln")
    op.drop_table("epss", schema="vuln")
    op.drop_table("cves", schema="vuln")
