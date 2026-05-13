"""initial auth schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "auth"


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("permissions", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(128), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.roles.id"), nullable=False),
        sa.Column("supplementary_permissions", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )

    op.create_table(
        "service_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.roles.id"), nullable=False),
        sa.Column("supplementary_permissions", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("bootstrap_token_hash", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )

    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        schema=SCHEMA,
    )

    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("actor", sa.String(256), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("target", sa.Text, nullable=True),
        sa.Column(
            "at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("details", JSONB, nullable=False, server_default="{}"),
        schema=SCHEMA,
    )

    op.create_index("ix_users_username", "users", ["username"], schema=SCHEMA)
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], schema=SCHEMA)
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"], schema=SCHEMA)
    op.create_index("ix_service_accounts_name", "service_accounts", ["name"], schema=SCHEMA)
    op.create_index("ix_audit_log_actor", "audit_log", ["actor"], schema=SCHEMA)
    op.create_index("ix_audit_log_at", "audit_log", ["at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("audit_log", schema=SCHEMA)
    op.drop_table("sessions", schema=SCHEMA)
    op.drop_table("service_accounts", schema=SCHEMA)
    op.drop_table("users", schema=SCHEMA)
    op.drop_table("roles", schema=SCHEMA)
