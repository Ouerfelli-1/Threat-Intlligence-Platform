# Performance Characteristics

This document states the performance-relevant behaviour of each layer, with
every quantitative value labelled **[configured]**, **[target]**,
**[measured]**, or **[inferred]** per the convention in `overview.md`.

## Web / API layer

| Characteristic | Value | Label |
|---|---|---|
| Concurrency model | async event loop (one per container) | configured |
| Per-request overhead | correlation middleware + auth (edge) + Pydantic validate | inferred (small) |
| Validation cost | Pydantic v2 (Rust core) | inferred (negligible vs I/O) |
| Health probe | `GET /health` returns a static dict | configured |

The async model means a single service process handles many concurrent
in-flight requests while they await I/O, rather than one-thread-per-request
(`12_technology_choices/async_stack.md`). Platform-side per-request CPU is
dominated by Pydantic (de)serialisation, which is fast enough to be ignored
next to network waits.

## Database layer

| Characteristic | Value | Label |
|---|---|---|
| Pool size per service | 10 + 15 overflow | configured |
| Pool timeout | 20s | configured |
| Connection recycle | 300s | configured |
| Pre-ping | on | configured |
| Prepared statements | disabled (`statement_cache_size=0`) | configured |
| Pooling mode | PgBouncer transaction pooling | configured |

The pool numbers (`10_implementation/database_implementation.md`) are sized
so that 15 services × their pools, multiplexed through PgBouncer, stay within
Postgres's connection ceiling. Disabling prepared statements is a
*correctness* requirement of transaction pooling, accepted at a small
per-query planning cost — a deliberate trade of micro-performance for pooling
scalability.

## Cache layer (Redis)

| Key | TTL | Purpose | Label |
|---|---|---|---|
| `ioc:<type>:<value>` | 10 min | hot lookup | configured |
| `cve:<id>` | 1 h | CVE summary | configured |
| `health:<svc>:<source>` | 60 s | circuit state (fast `is_open`) | configured |
| `ai:<sha256>` | 24 h | AI response cache | configured |
| `rl:<svc>:<key>` | per-window | rate limiting | configured |

The IOC lookup target is **sub-200ms [target]** — the design budget that
justified the Redis hot path so that Yassine gets an answer before switching
to VirusTotal (`01_introduction/stakeholders.md`). This target was the
*design driver*; it was not verified with a latency benchmark
(`benchmarks.md`).

## AI layer

| Characteristic | Value | Label |
|---|---|---|
| Per-call client timeout | 120s | configured |
| Insight related-data caps | actors 10, IOCs 25, articles 10, notes 20 | configured |
| AI cycle latency | seconds to minutes | inferred (provider-bound) |
| `/ask` example response | 1355 chars, substantive | measured (one observation) |
| Provider quotas | gpt-5-chat 12/day + 1 concurrent; gpt-4.1 ~50/day; gpt-4o 2 concurrent | measured (observed operating characteristics) |

AI latency is **provider-dominated** — the platform's contribution is the
context fan-out (a `gather` of fast local/HTTP reads) plus Pydantic
validation. The payload caps bound prompt size and therefore both latency and
token cost (`10_implementation/ai_implementation.md`). The cache-first design
means a viewed insight usually costs **zero** AI latency
(`caching_impact.md`).

## Ingestion layer

| Characteristic | Value | Label |
|---|---|---|
| Source concurrency | `asyncio.gather` across sources | configured |
| Retry policy | 3 attempts, 1s base, ×2 backoff, ±25% jitter | configured |
| Circuit breaker | 5 consecutive failures → degraded 30 min | configured |
| NVD full backfill (no key) | ~90 min | measured |
| Observed data volumes | ~241 articles, ~2028 IOCs, ~140 actors | measured (point-in-time) |

The ~90-minute NVD backfill **[measured]** is the clearest performance fact
in the project, and it is a *throughput* limit imposed by NVD's rate limit
without an API key, not a platform inefficiency (`bottlenecks.md`). The data
volumes are point-in-time observations from the running deployment, cited to
show the system handles realistic data, not as reproducible benchmarks.

## Frontend layer

| Characteristic | Value | Label |
|---|---|---|
| First load | SSR (App Router) | configured |
| Subsequent navigation | client-side transitions | configured |
| Data refresh | SWR `refetchInterval` (dashboard 30s, `/me` 15s, lists 60s) | configured |
| BFF hop | ~1–2ms within Docker network | inferred |
| Client-side list sort | over the fetched page only | configured |

The client-side sort (`11_testing` notes it) is an accepted trade: it sorts
the visible page, not the whole table, which is fine because lists fetch ≤200
rows — a deliberate simplicity-over-completeness choice.

## Summary

The platform's performance profile is: **fast cached/indexed reads, bounded
AI cost via caps + caching, throughput limits that are external (NVD rate
limit, AI quotas) rather than internal.** Every number above is either a
configured value or a single observation — none is a benchmarked
distribution, and `benchmarks.md` says so plainly.
