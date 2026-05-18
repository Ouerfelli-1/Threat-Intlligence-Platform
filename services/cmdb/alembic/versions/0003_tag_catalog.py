"""Admin-managed tag catalog. The tags applied to IOCs, assets, feeds,
articles, threats and actors must be drawn from this catalog so that
analyst-defined free-text tags don't drift over time.

Each tag carries a list of `scopes` (which resource types it applies to)
so 'finance-sector' can be limited to actors/threats while 'pci-dss' can
be limited to assets, etc.
"""
import sqlalchemy as sa
from alembic import op

revision = "0003_tag_catalog"
down_revision = "0002_profile_change_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tag_catalog",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(16), nullable=True),
        sa.Column(
            "scopes",
            sa.dialects.postgresql.ARRAY(sa.String),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.UniqueConstraint("name", name="uq_cmdb_tag_catalog_name"),
        schema="cmdb",
    )
    op.create_index(
        "ix_cmdb_tag_catalog_scopes_gin",
        "tag_catalog",
        ["scopes"],
        postgresql_using="gin",
        schema="cmdb",
    )

    # Seed a sensible default catalog so the system isn't empty on first deploy.
    op.execute("""
        INSERT INTO cmdb.tag_catalog (id, name, description, color, scopes, created_by)
        VALUES
          (gen_random_uuid(), 'ransomware',       'Ransomware-related',                 '#f85149', ARRAY['ioc','actor','threat','article','feed','cve'], 'system'),
          (gen_random_uuid(), 'phishing',         'Phishing campaign / kit / domain',   '#d29922', ARRAY['ioc','threat','article','feed'],               'system'),
          (gen_random_uuid(), 'supply_chain',     'Supply-chain compromise',            '#a371f7', ARRAY['ioc','threat','article','feed'],               'system'),
          (gen_random_uuid(), 'zero_day',         'Zero-day vulnerability',             '#f85149', ARRAY['threat','article','feed','cve'],               'system'),
          (gen_random_uuid(), 'data_breach',      'Public data breach disclosure',      '#d29922', ARRAY['threat','article','feed'],                     'system'),
          (gen_random_uuid(), 'c2',               'Command-and-control infrastructure', '#f85149', ARRAY['ioc'],                                         'system'),
          (gen_random_uuid(), 'botnet',           'Botnet membership / C2 node',        '#f85149', ARRAY['ioc','actor'],                                 'system'),
          (gen_random_uuid(), 'backdoor',         'Backdoor / RAT',                     '#f85149', ARRAY['ioc','threat','article'],                     'system'),
          (gen_random_uuid(), 'crown-jewel',      'Highest-value asset',                '#d29922', ARRAY['asset'],                                       'system'),
          (gen_random_uuid(), 'pci-dss',          'In PCI-DSS scope',                   '#58a6ff', ARRAY['asset'],                                       'system'),
          (gen_random_uuid(), 'core-banking',     'Core banking system',                '#d29922', ARRAY['asset'],                                       'system'),
          (gen_random_uuid(), 'internet-facing',  'Reachable from internet',            '#d29922', ARRAY['asset'],                                       'system'),
          (gen_random_uuid(), 'soc-observed',     'Confirmed by SOC',                   '#3fb950', ARRAY['ioc','threat'],                                'system'),
          (gen_random_uuid(), 'ics',              'Industrial control systems',         '#a371f7', ARRAY['asset','article','feed','threat'],            'system'),
          (gen_random_uuid(), 'apt',              'Advanced persistent threat',         '#f85149', ARRAY['actor','threat','article','feed'],            'system'),
          (gen_random_uuid(), 'cve',              'Contains a CVE reference',           '#58a6ff', ARRAY['article','feed','threat'],                    'system'),
          (gen_random_uuid(), 'banking',          'Banking-sector related',             '#58a6ff', ARRAY['article','feed','threat','actor','asset'],   'system'),
          (gen_random_uuid(), 'critical-infrastructure', 'Critical infrastructure',     '#d29922', ARRAY['asset','article','feed','threat'],            'system');
    """)


def downgrade() -> None:
    op.drop_index("ix_cmdb_tag_catalog_scopes_gin", table_name="tag_catalog", schema="cmdb")
    op.drop_table("tag_catalog", schema="cmdb")
