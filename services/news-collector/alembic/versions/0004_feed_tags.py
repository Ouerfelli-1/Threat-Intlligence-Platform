"""Add tags column to feeds. Feed-level tags are merged into every
article ingested from the feed (in addition to the per-article keyword tags)."""
import sqlalchemy as sa
from alembic import op

revision = "0004_feed_tags"
down_revision = "0003_analyst_layer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "feeds",
        sa.Column(
            "tags",
            sa.dialects.postgresql.ARRAY(sa.String),
            nullable=False,
            server_default="{}",
        ),
        schema="news",
    )


def downgrade() -> None:
    op.drop_column("feeds", "tags", schema="news")
