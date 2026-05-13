"""initial flowviz schema"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS flowviz")

    op.create_table(
        "flows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("input_text", sa.Text, nullable=False),
        sa.Column("output", postgresql.JSONB, nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("input_hash", name="uq_flowviz_flows_input_hash"),
        schema="flowviz",
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
        schema="flowviz",
    )


def downgrade() -> None:
    op.drop_table("source_health", schema="flowviz")
    op.drop_table("flows", schema="flowviz")
