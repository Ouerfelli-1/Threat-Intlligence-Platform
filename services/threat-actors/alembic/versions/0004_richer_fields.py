"""Add description + ransomware profile fields + actor correlation FK."""
import sqlalchemy as sa
from alembic import op

revision = "0004_richer_fields"
down_revision = "0003_analyst_layer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Actor description (textual profile from MITRE) ---
    op.add_column(
        "actors",
        sa.Column("description", sa.Text(), nullable=True),
        schema="actors",
    )

    # --- Tool description was already there. Add malpedia url for tools. ---
    op.add_column(
        "tools",
        sa.Column("malpedia_url", sa.String(512), nullable=True),
        schema="actors",
    )

    # --- Ransomware group richer profile ---
    op.add_column(
        "ransomware_groups",
        sa.Column("description", sa.Text(), nullable=True),
        schema="actors",
    )
    op.add_column(
        "ransomware_groups",
        sa.Column("profile_url", sa.String(512), nullable=True),
        schema="actors",
    )
    op.add_column(
        "ransomware_groups",
        sa.Column(
            "tor_urls",
            sa.dialects.postgresql.ARRAY(sa.String),
            nullable=False,
            server_default="{}",
        ),
        schema="actors",
    )
    op.add_column(
        "ransomware_groups",
        sa.Column(
            "domains",
            sa.dialects.postgresql.ARRAY(sa.String),
            nullable=False,
            server_default="{}",
        ),
        schema="actors",
    )
    op.add_column(
        "ransomware_groups",
        sa.Column(
            "locations",
            sa.dialects.postgresql.ARRAY(sa.String),
            nullable=False,
            server_default="{}",
        ),
        schema="actors",
    )
    op.add_column(
        "ransomware_groups",
        sa.Column(
            "iocs",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        schema="actors",
    )
    # Aggregated counts/dimensions derived from victims (denormalized for speed)
    op.add_column(
        "ransomware_groups",
        sa.Column("victim_count", sa.Integer(), nullable=False, server_default="0"),
        schema="actors",
    )
    op.add_column(
        "ransomware_groups",
        sa.Column(
            "target_countries",
            sa.dialects.postgresql.ARRAY(sa.String),
            nullable=False,
            server_default="{}",
        ),
        schema="actors",
    )
    op.add_column(
        "ransomware_groups",
        sa.Column(
            "target_sectors",
            sa.dialects.postgresql.ARRAY(sa.String),
            nullable=False,
            server_default="{}",
        ),
        schema="actors",
    )
    # Correlation to MITRE intrusion-set (nullable; not every ransomware group is a MITRE actor)
    op.add_column(
        "ransomware_groups",
        sa.Column("actor_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        schema="actors",
    )
    op.create_foreign_key(
        "fk_actors_ransomware_groups_actor_id",
        "ransomware_groups",
        "actors",
        ["actor_id"],
        ["id"],
        source_schema="actors",
        referent_schema="actors",
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_actors_ransomware_groups_actor_id",
        "ransomware_groups",
        ["actor_id"],
        schema="actors",
    )


def downgrade() -> None:
    op.drop_index("ix_actors_ransomware_groups_actor_id", table_name="ransomware_groups", schema="actors")
    op.drop_constraint("fk_actors_ransomware_groups_actor_id", "ransomware_groups", schema="actors")
    op.drop_column("ransomware_groups", "actor_id", schema="actors")
    op.drop_column("ransomware_groups", "target_sectors", schema="actors")
    op.drop_column("ransomware_groups", "target_countries", schema="actors")
    op.drop_column("ransomware_groups", "victim_count", schema="actors")
    op.drop_column("ransomware_groups", "iocs", schema="actors")
    op.drop_column("ransomware_groups", "locations", schema="actors")
    op.drop_column("ransomware_groups", "domains", schema="actors")
    op.drop_column("ransomware_groups", "tor_urls", schema="actors")
    op.drop_column("ransomware_groups", "profile_url", schema="actors")
    op.drop_column("ransomware_groups", "description", schema="actors")
    op.drop_column("tools", "malpedia_url", schema="actors")
    op.drop_column("actors", "description", schema="actors")
