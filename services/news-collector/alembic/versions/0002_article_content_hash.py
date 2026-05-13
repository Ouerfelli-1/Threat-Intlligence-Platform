"""add content_hash + updated_at to articles for enrichment tracking"""
import sqlalchemy as sa
from alembic import op

revision = "0002_article_content_hash"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("content_hash", sa.String(64), nullable=True),
        schema="news",
    )
    op.add_column(
        "articles",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        schema="news",
    )
    # Backfill content_hash for existing rows.
    # convert_to(text, 'UTF8') safely encodes any unicode to bytea — '::bytea' would
    # reject non-ASCII characters with "invalid input syntax for type bytea".
    op.execute(
        """
        UPDATE news.articles
        SET content_hash = encode(sha256(convert_to(COALESCE(content_text, ''), 'UTF8')), 'hex')
        WHERE content_hash IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("articles", "updated_at", schema="news")
    op.drop_column("articles", "content_hash", schema="news")
