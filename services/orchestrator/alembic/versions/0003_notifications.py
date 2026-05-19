"""notification_rules + notification_dispatches tables

Adds a configurable notification system. Event sources (domainwatch,
vuln-intel, threat-intel) emit events to orchestrator's /internal/notify;
the orchestrator looks up matching active rules and dispatches through
their channels (v1: SMTP). Every send is logged to notification_dispatches
for audit + retry-on-failure.
"""
import sqlalchemy as sa
from alembic import op

revision = "0003_notifications"
down_revision = "0002_ai_policies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_rules",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        # Display name only; logic keys off (event_type, channel, target).
        sa.Column("name", sa.String(128), nullable=False),
        # Event types: domainwatch.change | cve.exploited | threat.supply_chain
        # (More can be added without a schema change — kept as free string.)
        sa.Column("event_type", sa.String(64), nullable=False),
        # Channel: smtp | telegram | webhook (v1 ships smtp only).
        sa.Column("channel", sa.String(32), nullable=False),
        # Channel-specific destination — email address, telegram chat id,
        # webhook URL. Kept as text so we don't need a channel-table per type.
        sa.Column("target", sa.Text, nullable=False),
        # Optional per-event filter expressed as JSON. Examples:
        #   {"severity_min": "high"}        — cve.exploited
        #   {"change_types": ["dns","content"]}  — domainwatch.change
        #   {"product_match": true}         — only fire when threat affects
        #                                     a product in our CMDB profile
        sa.Column("filter", sa.dialects.postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="orchestrator",
    )
    op.create_index(
        "ix_notification_rules_event_active",
        "notification_rules",
        ["event_type", "active"],
        schema="orchestrator",
    )

    op.create_table(
        "notification_dispatches",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        # Nullable because manual/test sends don't go through a rule.
        sa.Column("rule_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        # Free-text reference to the underlying record (e.g. CVE-2024-3400,
        # threat UUID, domain UUID) — lets the UI link back to the source.
        sa.Column("event_ref", sa.String(256), nullable=True),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("target", sa.Text, nullable=False),
        # Status: sent | failed | skipped
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        # Snapshot of the event payload at dispatch time so the UI can show
        # what the analyst was notified about without doing extra joins.
        sa.Column("payload", sa.dialects.postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="orchestrator",
    )
    op.create_index(
        "ix_notification_dispatches_sent_at",
        "notification_dispatches",
        [sa.text("sent_at DESC")],
        schema="orchestrator",
    )


def downgrade() -> None:
    op.drop_index("ix_notification_dispatches_sent_at", table_name="notification_dispatches", schema="orchestrator")
    op.drop_table("notification_dispatches", schema="orchestrator")
    op.drop_index("ix_notification_rules_event_active", table_name="notification_rules", schema="orchestrator")
    op.drop_table("notification_rules", schema="orchestrator")
