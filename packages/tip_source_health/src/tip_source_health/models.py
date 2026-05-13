from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table


def build_source_health_table(metadata: MetaData, table_name: str = "source_health") -> Table:
    return Table(
        table_name,
        metadata,
        Column("source_name", String(128), primary_key=True),
        Column("last_success_at", DateTime(timezone=True), nullable=True),
        Column("last_failure_at", DateTime(timezone=True), nullable=True),
        Column("consecutive_failures", Integer, nullable=False, default=0, server_default="0"),
        Column("status", String(16), nullable=False, default="active", server_default="active"),
        Column("last_error", String(2048), nullable=True),
        Column("last_http_status", Integer, nullable=True),
        Column("updated_at", DateTime(timezone=True), nullable=True),
    )
