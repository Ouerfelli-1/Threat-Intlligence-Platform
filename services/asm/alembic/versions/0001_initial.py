"""initial asm schema"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS asm")

    op.create_table(
        "scopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("config", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="asm",
    )

    op.create_table(
        "targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("value", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["scope_id"], ["asm.scopes.id"], ondelete="CASCADE", name="fk_asm_targets_scope_id"),
        schema="asm",
    )
    op.create_index("ix_asm_targets_scope_type", "targets", ["scope_id", "type"], schema="asm")

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("findings_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text, nullable=True),
        sa.ForeignKeyConstraint(["scope_id"], ["asm.scopes.id"], ondelete="SET NULL", name="fk_asm_jobs_scope_id"),
        schema="asm",
    )
    op.create_index("ix_asm_jobs_status", "jobs", ["status"], schema="asm")

    op.create_table(
        "findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("value", sa.String(512), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("details", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.ForeignKeyConstraint(["job_id"], ["asm.jobs.id"], ondelete="CASCADE", name="fk_asm_findings_job_id"),
        sa.ForeignKeyConstraint(["target_id"], ["asm.targets.id"], ondelete="SET NULL", name="fk_asm_findings_target_id"),
        schema="asm",
    )
    op.create_index("ix_asm_findings_type", "findings", ["type"], schema="asm")
    op.create_index("ix_asm_findings_discovered_at", "findings", ["discovered_at"], schema="asm")

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
        schema="asm",
    )


def downgrade() -> None:
    op.drop_table("source_health", schema="asm")
    op.drop_table("findings", schema="asm")
    op.drop_table("jobs", schema="asm")
    op.drop_table("targets", schema="asm")
    op.drop_table("scopes", schema="asm")
