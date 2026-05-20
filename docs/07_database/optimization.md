# Database Optimization

## Optimization posture

At the customer's data scale (tens of thousands of rows), the database is
not the bottleneck — the AI provider quota is. Database optimization is
therefore targeted at the few hot paths, not applied uniformly.

## Applied optimizations

### 1. The IOC lookup never hits Postgres on a hit
The single latency-critical query (IOC lookup) is fronted by Redis. On a
cache hit, Postgres is not touched at all. On a miss, it is an index-only
equality lookup on `(type, normalized_value)`, then the result is cached.

### 2. Connection multiplexing
PgBouncer transaction pooling keeps the Postgres connection count low
regardless of how many service replicas exist, preventing connection
exhaustion under burst.

### 3. Idempotent upserts avoid read-modify-write races
Ingest writes use `ON CONFLICT DO UPDATE`, a single round-trip, instead of
SELECT-then-INSERT/UPDATE. This halves the round-trips on the write-heavy
ingest path and removes a race window.

### 4. Per-feed session scoping
Ingest commits per feed, so a large cycle is a series of small
transactions rather than one giant transaction holding locks for the whole
cycle.

### 5. Periodic commit in long backfills
The KEV backfill commits every 25 rows, bounding transaction size and
making a multi-hour run recoverable mid-flight.

### 6. EPSS full-replace instead of per-row diff
EPSS is a fresh global ranking each day; the ingester replaces all rows
rather than diffing — simpler and faster than computing per-row deltas
for a 300K-row dataset.

## Deferred optimizations (documented, not applied)

| Optimization | Why deferred | Trigger to apply |
|---|---|---|
| tsvector full-text index | `ILIKE` is fine at current article/CVE volume | article count → tens of thousands |
| Read replica for read-heavy services | single instance is idle most of the time | sustained read load |
| Partitioning large tables (cves) | 39K rows is small | rows → millions |
| GIN index on JSONB insight payloads | payloads read by PK only | a query that filters by inner JSON field |
| Per-service Postgres instances | schema-per-service makes this a config change | one service becomes a noisy neighbour |

## Measurement honesty

No formal load test was run against the database. The optimization claims
are:
- **Measured:** cached IOC lookup is single-digit ms; cached AI insight
  re-open ~0.1–0.2s (observed during development).
- **Inferred:** the database has substantial headroom at the design point
  because the workload is bursty and small; steady-state CPU is low.

The honest statement: the database is **not** the platform's scaling
constraint at the design point, so it has not been aggressively tuned. The
tuning levers (indexes, replicas, partitioning) are identified and ready
if the data volume grows by orders of magnitude.

## Vacuum / maintenance

Postgres autovacuum handles the write-heavy ingest tables. The
operator's only database maintenance responsibility is backing up the
`postgres-data` volume; no manual VACUUM or REINDEX is required at this
scale.
