# Indexing Strategy

## Principle: index the query, not the table

Indexes are added where the access pattern demands them, derived from the
actual route filters and joins, not speculatively.

## Uniqueness constraints as the first line

Several "indexes" are uniqueness constraints that double as lookup
indexes:

| Constraint | Schema.table | Serves |
|---|---|---|
| `unique(type, normalized_value)` | ioc.indicators | the hot-path lookup join key |
| `url_hash unique` | news.articles | dedup + lookup |
| `cve_id pk` | vuln.cves / epss / kev | merge of CVE+EPSS+KEV by id |
| partial unique `WHERE mitre_id IS NOT NULL` | actors.actors | STIX uniqueness while allowing manual NULL |
| `name pk` | secrets.secrets | vault fetch by name |
| `pk(indicator_id, source_name)` | ioc.indicator_sources | corroboration counting |
| `dedup_key unique` | actors.ransomware_victims | victim dedup |

## Explicit indexes from migrations

Observed in the migrations (`services/*/alembic/versions/*.py`):

| Index | Purpose |
|---|---|
| `ix_ai_policies_scope_priority (scope, priority DESC)` | policy resolution order |
| `ix_ai_policies_resource (resource_type, resource_id)` | per-resource policy lookup |
| `ix_notification_rules_event_active (event_type, active)` | dispatch rule lookup |
| `ix_notification_dispatches_sent_at (sent_at DESC)` | recent-dispatch history |
| `ix_dork_runs_target (target, target_type)` | dork history by target |
| `ix_dork_runs_started_at (started_at DESC)` | recent dork runs |
| `ix_dork_findings_run_id (run_id)` | findings for a run |
| analyst-layer indexes on `analyst_status` | list filters that exclude `not_relevant` |

## The hot-path index that matters most

`ioc.indicators (type, normalized_value)` unique — this backs the IOC
lookup. On a cache miss the query is an index-only equality lookup, which
is why the Postgres fallback is still fast enough that the 200 ms budget
holds even cold.

## Time-ordered list indexes

Most list endpoints sort by a timestamp DESC (`observed_at`,
`last_seen`, `published_at`, `sent_at`, `started_at`). The `DESC` indexes
on these columns serve the default "newest first" view without a sort
step.

## What is deliberately not indexed

- **Full-text search** on article/threat bodies uses `ILIKE '%q%'`, not a
  GIN/tsvector index. At the customer's data volume (hundreds of
  articles, thousands of CVEs) a sequential `ILIKE` is acceptable;
  introducing a tsvector index is a documented future optimisation
  (`13_performance/database_performance.md`).
- **JSONB payloads** (insight payloads, confidence_inputs) are not
  GIN-indexed — they are read by primary key, never queried by inner
  field on the hot path.

## Index maintenance posture

Indexes are created in the same migration that creates the table or adds
the queried column. There is no separate index-tuning migration; the
strategy is "add the index when the query is added". This keeps the index
set minimal and intentional, avoiding the write-amplification of
speculative indexing on a write-heavy ingest path.
