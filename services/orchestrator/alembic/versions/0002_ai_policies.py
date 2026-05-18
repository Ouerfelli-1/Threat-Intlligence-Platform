"""ai_policies + action_runs tables; seed global default policy"""
import uuid
import sqlalchemy as sa
from alembic import op

revision = "0002_ai_policies"
down_revision = "0001"
branch_labels = None
depends_on = None

GLOBAL_POLICY_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.create_table(
        "ai_policies",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("actions", sa.dialects.postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("cmdb_filter", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="orchestrator",
    )
    op.create_index(
        "ix_ai_policies_scope_priority",
        "ai_policies",
        ["scope", sa.text("priority DESC")],
        schema="orchestrator",
    )
    op.create_index(
        "ix_ai_policies_resource",
        "ai_policies",
        ["resource_type", "resource_id"],
        schema="orchestrator",
    )

    op.create_table(
        "action_runs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("output", sa.dialects.postgresql.JSONB, nullable=True),
        schema="orchestrator",
    )

    # Seed the global default policy: full_auto with all actions
    op.execute(
        f"""
        INSERT INTO orchestrator.ai_policies (id, scope, mode, actions, priority, active)
        VALUES (
            '{GLOBAL_POLICY_ID}',
            'global',
            'full_auto',
            ARRAY['cve_relevance','actor_likelihood','correlation','brief','flowviz','extract_iocs','map_ttps','hunting_hypothesis','check_kev_exploited']::text[],
            0,
            true
        )
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("action_runs", schema="orchestrator")
    op.drop_table("ai_policies", schema="orchestrator")
