"""initial news schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-12 00:00:00
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS news")

    op.create_table(
        "feeds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False, unique=True),
        sa.Column("kind", sa.String(32), nullable=False, server_default="rss"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("reliability", sa.Numeric(3, 2), nullable=False, server_default="0.70"),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_pulled_at", sa.DateTime(timezone=True), nullable=True),
        schema="news",
    )

    op.create_table(
        "articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("url_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("source_feed_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_name", sa.String(128), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("content_text", sa.Text, nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("confidence_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("confidence_inputs", postgresql.JSONB, nullable=True),
        schema="news",
    )
    op.create_index("ix_news_articles_published_at", "articles", ["published_at"], schema="news")
    op.create_index("ix_news_articles_source_name", "articles", ["source_name"], schema="news")
    op.create_index("ix_news_articles_tags", "articles", ["tags"], schema="news", postgresql_using="gin")

    op.create_table(
        "article_insights",
        sa.Column("article_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("model_name", sa.String(128), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="news",
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
        schema="news",
    )


def downgrade() -> None:
    op.drop_table("source_health", schema="news")
    op.drop_table("article_insights", schema="news")
    op.drop_table("articles", schema="news")
    op.drop_table("feeds", schema="news")
