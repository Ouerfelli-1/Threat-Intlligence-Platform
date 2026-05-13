"""add dedup_key to ransomware_victims"""
import sqlalchemy as sa
from alembic import op

revision = "0002_ransomware_victims_dedup"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add a deterministic dedup hash. NULL allowed until backfill complete.
    op.add_column(
        "ransomware_victims",
        sa.Column("dedup_key", sa.String(64), nullable=True),
        schema="actors",
    )
    # Backfill existing rows: sha256(group_id::text || '|' || victim_name || '|' || coalesce(disclosed_at::text, ''))
    op.execute(
        """
        UPDATE actors.ransomware_victims
        SET dedup_key = encode(
            sha256(
                (group_id::text || '|' || victim_name || '|' || COALESCE(disclosed_at::text, ''))::bytea
            ),
            'hex'
        )
        WHERE dedup_key IS NULL
        """
    )
    # Drop duplicate rows that share the same dedup_key (keep oldest by id ORDER BY ctid)
    op.execute(
        """
        DELETE FROM actors.ransomware_victims a
        USING actors.ransomware_victims b
        WHERE a.ctid > b.ctid
          AND a.dedup_key = b.dedup_key
        """
    )
    op.alter_column(
        "ransomware_victims", "dedup_key",
        nullable=False, schema="actors",
    )
    op.create_index(
        "uq_actors_ransomware_victims_dedup_key",
        "ransomware_victims",
        ["dedup_key"],
        unique=True,
        schema="actors",
    )


def downgrade() -> None:
    op.drop_index(
        "uq_actors_ransomware_victims_dedup_key",
        table_name="ransomware_victims",
        schema="actors",
    )
    op.drop_column("ransomware_victims", "dedup_key", schema="actors")
