"""initial domainwatch schema"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS domainwatch")

    op.create_table(
        "domains",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("name", name="uq_domainwatch_domains_name"),
        schema="domainwatch",
    )

    op.create_table(
        "snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("domain_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("details", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("screenshot_path", sa.String(1024), nullable=True),
        sa.ForeignKeyConstraint(["domain_id"], ["domainwatch.domains.id"], ondelete="CASCADE", name="fk_domainwatch_snapshots_domain_id"),
        schema="domainwatch",
    )
    op.create_index("ix_domainwatch_snapshots_domain_captured", "snapshots", ["domain_id", "captured_at"], schema="domainwatch")

    op.create_table(
        "changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("domain_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("change_type", sa.String(64), nullable=False),
        sa.Column("before", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("after", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.ForeignKeyConstraint(["domain_id"], ["domainwatch.domains.id"], ondelete="CASCADE", name="fk_domainwatch_changes_domain_id"),
        schema="domainwatch",
    )
    op.create_index("ix_domainwatch_changes_detected_at", "changes", ["detected_at"], schema="domainwatch")

    op.create_table(
        "domain_iocs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("domain_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ioc_type", sa.String(32), nullable=False),
        sa.Column("value", sa.String(2048), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["domain_id"], ["domainwatch.domains.id"], ondelete="CASCADE", name="fk_domainwatch_domain_iocs_domain_id"),
        schema="domainwatch",
    )

    op.create_table(
        "domain_subdomains",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("domain_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subdomain", sa.String(512), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["domain_id"], ["domainwatch.domains.id"], ondelete="CASCADE", name="fk_domainwatch_domain_subdomains_domain_id"),
        schema="domainwatch",
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
        schema="domainwatch",
    )


def downgrade() -> None:
    op.drop_table("source_health", schema="domainwatch")
    op.drop_table("domain_subdomains", schema="domainwatch")
    op.drop_table("domain_iocs", schema="domainwatch")
    op.drop_table("changes", schema="domainwatch")
    op.drop_table("snapshots", schema="domainwatch")
    op.drop_table("domains", schema="domainwatch")
