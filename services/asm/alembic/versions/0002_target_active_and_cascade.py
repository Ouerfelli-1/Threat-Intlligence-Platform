"""asm: per-target active toggle, plus cascade from scope -> jobs -> findings.

  * Adds asm.targets.active (default true). Existing rows keep being scanned.
  * Changes the asm.jobs.scope_id FK from SET NULL to CASCADE so that
    deleting a scope now removes its jobs (and findings cascade off jobs).
    Before this, deleting a scope orphaned its jobs and findings forever.
"""
import sqlalchemy as sa
from alembic import op


revision = "0002_target_active_and_cascade"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. Target active toggle -------------------------------------------
    op.add_column(
        "targets",
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        schema="asm",
    )

    # --- 2. Jobs FK: SET NULL -> CASCADE -----------------------------------
    # Postgres requires drop + add; the constraint name was set by 0001 via
    # ForeignKeyConstraint(name=...) and matches what we recreate here.
    op.drop_constraint("fk_asm_jobs_scope_id", "jobs", schema="asm", type_="foreignkey")
    op.create_foreign_key(
        "fk_asm_jobs_scope_id",
        source_table="jobs",
        referent_table="scopes",
        local_cols=["scope_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
        source_schema="asm",
        referent_schema="asm",
    )

    # Make scope_id NOT NULL — under SET NULL it could legitimately be null
    # (orphaned jobs), but with CASCADE every job is tied to a live scope.
    # Backfill orphans by removing them so the NOT NULL is safe.
    op.execute("DELETE FROM asm.jobs WHERE scope_id IS NULL")
    op.alter_column(
        "jobs", "scope_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=False,
        schema="asm",
    )


def downgrade() -> None:
    op.alter_column(
        "jobs", "scope_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
        schema="asm",
    )
    op.drop_constraint("fk_asm_jobs_scope_id", "jobs", schema="asm", type_="foreignkey")
    op.create_foreign_key(
        "fk_asm_jobs_scope_id",
        source_table="jobs",
        referent_table="scopes",
        local_cols=["scope_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
        source_schema="asm",
        referent_schema="asm",
    )

    op.drop_column("targets", "active", schema="asm")
