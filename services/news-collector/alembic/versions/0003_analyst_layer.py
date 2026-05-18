"""analyst_status + notes table + insight override for articles"""
import sqlalchemy as sa
from alembic import op

revision = "0003_analyst_layer"
down_revision = "0002_article_content_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # analyst_status on articles
    op.add_column(
        "articles",
        sa.Column("analyst_status", sa.String(32), nullable=False, server_default="unreviewed"),
        schema="news",
    )
    op.create_index("ix_news_articles_analyst_status", "articles", ["analyst_status"], schema="news")

    # analyst_override on article_insights
    op.add_column(
        "article_insights",
        sa.Column("analyst_override", sa.dialects.postgresql.JSONB, nullable=True),
        schema="news",
    )

    # article_notes table
    op.create_table(
        "article_notes",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("article_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("pinned", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("author", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="news",
    )
    op.create_index("ix_news_article_notes_article_id_pinned", "article_notes", ["article_id", "pinned"], schema="news")


def downgrade() -> None:
    op.drop_table("article_notes", schema="news")
    op.drop_column("article_insights", "analyst_override", schema="news")
    op.drop_index("ix_news_articles_analyst_status", table_name="articles", schema="news")
    op.drop_column("articles", "analyst_status", schema="news")
