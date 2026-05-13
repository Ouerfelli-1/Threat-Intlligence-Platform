"""initial scheduler schema"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS scheduler")

    op.create_table(
        "job_run_history",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", sa.String(128), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="running"),
        sa.Column("http_status", sa.Integer, nullable=True),
        sa.Column("error_detail", sa.Text, nullable=True),
        schema="scheduler",
    )
    op.create_index("ix_scheduler_job_run_history_job_id", "job_run_history", ["job_id"], schema="scheduler")
    op.create_index("ix_scheduler_job_run_history_status", "job_run_history", ["status"], schema="scheduler")
    op.create_index("ix_scheduler_job_run_history_triggered_at", "job_run_history", ["triggered_at"], schema="scheduler")


def downgrade() -> None:
    op.drop_table("job_run_history", schema="scheduler")
