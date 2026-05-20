"""dork_runs + dork_findings tables for the Google-dorking sub-investigation.

One DorkRun per /dorks/run invocation, many DorkFindings underneath. Kept
separate from the existing Investigation table because dorking is its own
workflow (sometimes you don't want a full passive enrichment, just dorks).
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_dorking"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dork_runs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("target", sa.Text, nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),  # domain | email | ip | company
        sa.Column("categories", sa.dialects.postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        # Backend that ACTUALLY served the bulk of queries (may differ from
        # the preferred one when fallback kicks in). Values: google | duckduckgo | mixed.
        sa.Column("backend", sa.String(32), nullable=False, server_default="duckduckgo"),
        # success | degraded | failed.  degraded = some queries hit
        # rate-limits and fell back / were dropped.
        sa.Column("status", sa.String(32), nullable=False, server_default="success"),
        sa.Column("total_findings", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        schema="indicator",
    )
    op.create_index(
        "ix_dork_runs_target",
        "dork_runs",
        ["target", "target_type"],
        schema="indicator",
    )
    op.create_index(
        "ix_dork_runs_started_at",
        "dork_runs",
        [sa.text("started_at DESC")],
        schema="indicator",
    )

    op.create_table(
        "dork_findings",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        # The actual dork query that surfaced this finding (so the analyst
        # can see how each link was discovered).
        sa.Column("dork", sa.Text, nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("title", sa.Text, nullable=False, server_default=""),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("snippet", sa.Text, nullable=False, server_default=""),
        sa.Column("source", sa.String(32), nullable=False),  # google | duckduckgo
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["run_id"], ["indicator.dork_runs.id"], ondelete="CASCADE",
            name="fk_indicator_dork_findings_run_id",
        ),
        schema="indicator",
    )
    op.create_index(
        "ix_dork_findings_run_id",
        "dork_findings",
        ["run_id"],
        schema="indicator",
    )


def downgrade() -> None:
    op.drop_index("ix_dork_findings_run_id", table_name="dork_findings", schema="indicator")
    op.drop_table("dork_findings", schema="indicator")
    op.drop_index("ix_dork_runs_started_at", table_name="dork_runs", schema="indicator")
    op.drop_index("ix_dork_runs_target", table_name="dork_runs", schema="indicator")
    op.drop_table("dork_runs", schema="indicator")
