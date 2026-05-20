# Database Implementation

The data layer is **async SQLAlchemy 2.x over asyncpg, through PgBouncer in
transaction-pooling mode**. This document covers the real engine
configuration and the implementation decisions it forces. The schema design
itself is in `07_database`.

## The engine — tuned for PgBouncer

`tip_db.build_async_engine` is the single place every service's engine is
created. The configuration is not default — every argument is there for a
reason tied to PgBouncer:

```python
create_async_engine(
    url,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=10,
    max_overflow=15,
    pool_timeout=20,
    connect_args={"statement_cache_size": 0,
                  "prepared_statement_cache_size": 0},
)
```

| Setting | Value | Why |
|---|---|---|
| `statement_cache_size` | `0` | **Transaction pooling forbids prepared statements** — a pooled backend is not stably the same one across calls. This is the load-bearing setting. |
| `prepared_statement_cache_size` | `0` | same reason, asyncpg's other cache |
| `pool_pre_ping` | `True` | PgBouncer closes idle backends under the client; pre-ping rebuilds them before use |
| `pool_recycle` | `300` | bound connection age so a silently-killed idle connection is never reused (avoids asyncpg's brief cached-failure window) |
| `pool_size` / `max_overflow` | `10` / `15` | per-service ceiling; 15 services × this is why PgBouncer exists at all |
| `pool_timeout` | `20` | fail fast rather than hang when the pool is exhausted |

The two `statement_cache_size=0` arguments are the single most important
implementation detail in the data layer. Without them, asyncpg prepares
statements that PgBouncer cannot guarantee will execute on the same backend,
producing intermittent `prepared statement "__asyncpg_*__" does not exist`
errors under load.

## Two engines in one service: the scheduler exception

Every service uses the async engine above. The **scheduler** additionally
builds a **synchronous** engine (psycopg2) for APScheduler's
`SQLAlchemyJobStore`, because APScheduler 3.x's job store is sync-only.
`Settings.sync_db_url` derives the psycopg2 URL from the async one. This is
the one place a service runs two engines side by side, documented as a known
wart in `06_services/scheduler_service` (APScheduler 4 is async-native but
still beta).

## Session lifecycle

The `get_session` dependency (`backend_implementation.md`) owns the
transaction: yield → commit on success, rollback on exception. Sessions use
`expire_on_commit=False` and `autoflush=False`:

| Option | Value | Effect |
|---|---|---|
| `expire_on_commit` | `False` | ORM objects stay usable after commit (so a handler can return a model it just committed without a re-SELECT) |
| `autoflush` | `False` | flushes are explicit, avoiding surprise mid-handler writes |

## Schema-per-service in code

Each service's models declare their schema. There are **no `ForeignKey`
declarations crossing schemas** — the `P1` invariant is enforced by absence,
not by configuration. Cross-service references are stored as stable string
IDs (CVE-ID, MITRE technique ID, normalized indicator value) and resolved by
HTTP, never by SQL join (`07_database/schema_design.md`).

Each service's Alembic config sets its own `version_table_schema` so the 15
per-service migration histories never collide in one shared
`alembic_version` table (`07_database/migrations.md`).

## JSONB as the flex column

Across the schema, volatile or provider-shaped data is stored in `JSONB`
columns (`raw`, `payload`, `details`, `confidence_inputs`, `config`). This is
a deliberate implementation choice: the relational columns carry the fields
the platform queries and indexes; JSONB carries the full upstream record so
nothing is lost and re-processing is possible without a re-fetch
(`07_database/optimization.md`).

## What the implementation deliberately avoids

- **No ORM relationships across schemas** — would imply cross-schema FKs.
- **No prepared statements** — incompatible with transaction pooling.
- **No long-lived sessions** — one session per request, transaction-scoped.
- **No raw connection sharing across requests** — the pool owns connections.
