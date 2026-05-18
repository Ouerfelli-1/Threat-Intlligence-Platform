"""analyst_status + notes table + insight override + mitre_id partial unique for actors"""
import sqlalchemy as sa
from alembic import op

revision = "0003_analyst_layer"
down_revision = "0002_ransomware_victims_dedup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # analyst_status on actors
    op.add_column(
        "actors",
        sa.Column("analyst_status", sa.String(32), nullable=False, server_default="unreviewed"),
        schema="actors",
    )
    op.create_index("ix_actors_actors_analyst_status", "actors", ["analyst_status"], schema="actors")

    # Drop old UNIQUE constraint on mitre_id; replace with partial unique
    op.drop_constraint("uq_actors_mitre_id", "actors", schema="actors")
    op.create_index(
        "ix_actors_mitre_id_unique",
        "actors",
        ["mitre_id"],
        unique=True,
        schema="actors",
        postgresql_where=sa.text("mitre_id IS NOT NULL"),
    )

    # analyst_override on actor_insights
    op.add_column(
        "actor_insights",
        sa.Column("analyst_override", sa.dialects.postgresql.JSONB, nullable=True),
        schema="actors",
    )

    # actor_notes table
    op.create_table(
        "actor_notes",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("pinned", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("author", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="actors",
    )
    op.create_index("ix_actors_actor_notes_actor_id_pinned", "actor_notes", ["actor_id", "pinned"], schema="actors")


def downgrade() -> None:
    op.drop_table("actor_notes", schema="actors")
    op.drop_column("actor_insights", "analyst_override", schema="actors")
    op.drop_index("ix_actors_mitre_id_unique", table_name="actors", schema="actors")
    op.create_unique_constraint("uq_actors_mitre_id", "actors", ["mitre_id"], schema="actors")
    op.drop_index("ix_actors_actors_analyst_status", table_name="actors", schema="actors")
    op.drop_column("actors", "analyst_status", schema="actors")
