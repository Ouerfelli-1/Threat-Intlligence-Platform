"""initial integrations schema"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS integrations")

    op.create_table(
        "wazuh_alerts",
        sa.Column("alert_id", sa.String(256), primary_key=True),
        sa.Column("agent_id", sa.String(64), nullable=True),
        sa.Column("agent_name", sa.String(256), nullable=True),
        sa.Column("rule_id", sa.String(64), nullable=True),
        sa.Column("rule_description", sa.String(1024), nullable=True),
        sa.Column("severity", sa.Integer, nullable=False, server_default="0"),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw", postgresql.JSONB, nullable=False, server_default="{}"),
        schema="integrations",
    )
    op.create_index("ix_integrations_wazuh_alerts_timestamp", "wazuh_alerts", ["timestamp"], schema="integrations")
    op.create_index("ix_integrations_wazuh_alerts_severity", "wazuh_alerts", ["severity"], schema="integrations")

    op.create_table(
        "wazuh_agents",
        sa.Column("agent_id", sa.String(64), primary_key=True),
        sa.Column("hostname", sa.String(256), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("os", sa.String(256), nullable=True),
        sa.Column("version", sa.String(64), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("raw", postgresql.JSONB, nullable=False, server_default="{}"),
        schema="integrations",
    )

    op.create_table(
        "misp_events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("info", sa.String(1024), nullable=True),
        sa.Column("threat_level_id", sa.Integer, nullable=True),
        sa.Column("analysis", sa.Integer, nullable=True),
        sa.Column("date", sa.Date, nullable=True),
        sa.Column("org", sa.String(256), nullable=True),
        sa.Column("raw", postgresql.JSONB, nullable=False, server_default="{}"),
        schema="integrations",
    )

    op.create_table(
        "misp_iocs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("normalized_value", sa.String(2048), nullable=False),
        sa.Column("raw_value", sa.String(2048), nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("to_ids", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("raw", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.UniqueConstraint("event_id", "type", "normalized_value", name="uq_integrations_misp_iocs"),
        sa.ForeignKeyConstraint(
            ["event_id"], ["integrations.misp_events.event_id"], ondelete="CASCADE",
            name="fk_integrations_misp_iocs_event_id",
        ),
        schema="integrations",
    )

    op.create_table(
        "misp_pushes",
        sa.Column("local_indicator_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("misp_event_id", sa.String(64), nullable=False),
        sa.Column("misp_attribute_id", sa.String(64), nullable=False),
        sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="integrations",
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
        schema="integrations",
    )


def downgrade() -> None:
    op.drop_table("source_health", schema="integrations")
    op.drop_table("misp_pushes", schema="integrations")
    op.drop_table("misp_iocs", schema="integrations")
    op.drop_table("misp_events", schema="integrations")
    op.drop_table("wazuh_agents", schema="integrations")
    op.drop_table("wazuh_alerts", schema="integrations")
