"""initial actors schema"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS actors")

    op.create_table(
        "actors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("mitre_id", sa.String(32), nullable=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("aliases", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("origin_country", sa.String(128), nullable=True),
        sa.Column("motivation", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("active_since", sa.Date, nullable=True),
        sa.Column("last_seen", sa.Date, nullable=True),
        sa.Column("target_sectors", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("target_countries", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("raw", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.UniqueConstraint("mitre_id", name="uq_actors_mitre_id"),
        schema="actors",
    )
    op.create_index("ix_actors_actors_name", "actors", ["name"], schema="actors")
    op.create_index("ix_actors_actors_status", "actors", ["status"], schema="actors")

    op.create_table(
        "tools",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("aliases", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("mitre_id", sa.String(32), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("raw", postgresql.JSONB, nullable=False, server_default="{}"),
        schema="actors",
    )

    op.create_table(
        "actor_ttps",
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("technique_id", sa.String(32), nullable=False),
        sa.Column("technique_name", sa.String(256), nullable=False),
        sa.Column("sub_technique_id", sa.String(32), nullable=True),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=False, server_default="0.50"),
        sa.Column("source", sa.String(128), nullable=False, server_default="mitre"),
        sa.PrimaryKeyConstraint("actor_id", "technique_id", name="pk_actors_actor_ttps"),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["actors.actors.id"], ondelete="CASCADE",
            name="fk_actors_actor_ttps_actor_id",
        ),
        schema="actors",
    )
    op.create_index("ix_actors_actor_ttps_technique", "actor_ttps", ["technique_id"], schema="actors")

    op.create_table(
        "actor_tools",
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("actor_id", "tool_id", name="pk_actors_actor_tools"),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["actors.actors.id"], ondelete="CASCADE",
            name="fk_actors_actor_tools_actor_id",
        ),
        sa.ForeignKeyConstraint(
            ["tool_id"], ["actors.tools.id"], ondelete="CASCADE",
            name="fk_actors_actor_tools_tool_id",
        ),
        schema="actors",
    )

    op.create_table(
        "ransomware_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("aliases", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("first_seen", sa.Date, nullable=True),
        sa.Column("last_seen", sa.Date, nullable=True),
        sa.Column("variants", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("leak_site_url", sa.String(512), nullable=True),
        sa.Column("ransom_range", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("raw", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.UniqueConstraint("name", name="uq_actors_ransomware_groups_name"),
        schema="actors",
    )

    op.create_table(
        "ransomware_victims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("victim_name", sa.String(256), nullable=False),
        sa.Column("sector", sa.String(128), nullable=True),
        sa.Column("country", sa.String(128), nullable=True),
        sa.Column("disclosed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(128), nullable=False, server_default="ransomware.live"),
        sa.Column("raw", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.ForeignKeyConstraint(
            ["group_id"], ["actors.ransomware_groups.id"], ondelete="CASCADE",
            name="fk_actors_ransomware_victims_group_id",
        ),
        schema="actors",
    )
    op.create_index("ix_actors_ransomware_victims_disclosed", "ransomware_victims", ["disclosed_at"], schema="actors")

    op.create_table(
        "actor_insights",
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["actors.actors.id"], ondelete="CASCADE",
            name="fk_actors_actor_insights_actor_id",
        ),
        schema="actors",
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
        schema="actors",
    )


def downgrade() -> None:
    op.drop_table("source_health", schema="actors")
    op.drop_table("actor_insights", schema="actors")
    op.drop_table("ransomware_victims", schema="actors")
    op.drop_table("ransomware_groups", schema="actors")
    op.drop_table("actor_tools", schema="actors")
    op.drop_table("actor_ttps", schema="actors")
    op.drop_table("tools", schema="actors")
    op.drop_table("actors", schema="actors")
