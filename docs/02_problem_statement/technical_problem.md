# Technical Problem

The business problem decomposes into a set of concrete technical problems,
each of which drove a specific architectural decision.

## TP1 — Heterogeneous, unreliable external sources

The platform must ingest from sources with wildly different shapes (RSS,
JSON APIs, CSV snapshots, STIX bundles, HTML scrapes) and reliability
profiles (CISA is near-100 %; vx-underground HTML scraping fails often).

**Constraint:** one slow or failing source must never stall or abort the
ingestion cycle.

**Resulting decision:** every outbound call goes through
`packages/tip_http/fetch_with_resilience.py` (timeout + retry + circuit
breaker), and ingestion cycles run sources with
`asyncio.gather(*tasks, return_exceptions=True)`. Per-service
`source_health` tables persist circuit-breaker state and mirror it to
Redis for a fast `is_open()` check.

## TP2 — Cross-source corroboration requires a canonical key

"Three independent sources report this domain" is only computable if the
three reports normalise to the same string. Raw feed values are
inconsistent (case, defanging, punycode, trailing dots).

**Resulting decision:** `tip_schemas.indicators.normalize` is the single
normalisation authority, called by every ingester before persistence.
The `ioc.indicators` table enforces `unique(type, normalized_value)` and
corroboration is counted from `ioc.indicator_sources` rows.

## TP3 — Latency-critical lookup vs. write-heavy ingest

The IOC lookup (Yassine's hot path) needs < 200 ms. The ingest path is
write-heavy and bursty. These two access patterns conflict if served
naively from the same Postgres queries.

**Resulting decision:** the lookup endpoint checks Redis first
(`ioc:<type>:<value>`, 10-minute TTL) and only falls back to Postgres on
a miss, repopulating the cache. Ingest writes go straight to Postgres
through PgBouncer.

## TP4 — 15 services × connection pool would exhaust Postgres

Fifteen services, each with its own SQLAlchemy async pool, would open far
more connections than a single Postgres instance tolerates.

**Resulting decision:** all services connect to **PgBouncer** (port 6432)
in *transaction* pooling mode, which multiplexes many client connections
onto few server connections. Because transaction pooling forbids
prepared statements, asyncpg is configured with `statement_cache_size=0`
in `packages/tip_db`.

## TP5 — AI must augment but never gate the platform

If the LLM provider rate-limits or goes down, the platform must keep
serving stored intelligence and keep ingesting. AI must be strictly
off the ingest hot path.

**Resulting decision:** AI is isolated behind `packages/tip_ai` and a
standalone **LiteLLM proxy** container. Ingesters never import `tip_ai`.
AI failures surface as typed exceptions (`LiteLLMRateLimitError`,
`LiteLLMRequestTooLargeError`, `LiteLLMError`) handled per-call so a 429
degrades one insight, not the platform.

## TP6 — Multiple AI providers, shared quota, flaky upstreams

GitHub Models (the default provider) imposes tight per-model daily quotas
(observed: 12/day for `gpt-5-chat`, ~50/day for `gpt-4.1`) and a
concurrent-request cap (observed: 1 for `gpt-5-chat`, 2 for `gpt-4o`).
A naive "always use the smartest model" strategy exhausts quota in four
clicks.

**Resulting decision (commit `61ba20a`):** a smart-model picker that
prefers `gpt-4.1` (largest quota) with `gpt-5-chat` as a reserve;
serialised multi-leg AI calls to respect the concurrency cap; and a
LiteLLM proxy fallback config that cascades *within* the same provider
before falling out to a different one. Insight results are cache-first
(`prompt_version`-keyed) so re-opening never re-bills the model.

## TP7 — Per-service schema isolation without losing join-ability

Services must own their data (no service reads another's tables), but the
platform still needs to relate a CVE in `vuln` to a threat in `threat`.

**Resulting decision:** one Postgres database, one schema per service,
**no foreign keys across schemas**. Cross-service relations use stable
external identifiers (CVE-IDs, MITRE technique IDs, normalised indicator
values). Cross-service data access is HTTP-only.

## TP8 — Bootstrapping secrets before any service has a token

The secrets vault needs to be readable by services that have not yet
authenticated — a chicken-and-egg problem.

**Resulting decision:** a shared `SECRETS_BOOTSTRAP_TOKEN` (in `.env`)
authorises a pre-auth `/internal/bootstrap-fetch` endpoint on the
`secrets` service. Each service fetches its own credentials at startup
using this token before it can do anything else.

## TP9 — Reproducible multi-service migration

Fifteen services each with their own Alembic migration directory must be
migrated in a single, ordered, idempotent step before any service starts.

**Resulting decision:** a one-shot `alembic-init` container
(`infra/alembic-init/`) iterates every service's migration directory and
runs them (order-independent — no cross-schema FKs). Other services
`depends_on: alembic-init: service_completed_successfully`.

## TP10 — The frontend must reach 15 back-ends without CORS sprawl

A browser SPA hitting 15 different service origins would require CORS
configuration on every service and would leak the internal topology.

**Resulting decision:** a Next.js **backend-for-frontend (BFF)** —
`frontend/src/app/api/[...path]/route.ts` — maps the first path segment
to the right internal service URL and proxies server-side. The browser
only ever talks to the frontend origin. After the auth simplification
(commit `5d216c1`) the BFF forwards the bearer token, auth validates it,
and the data services trust the docker network.

## Summary table

| Technical problem | Architectural response | Source of truth |
|---|---|---|
| TP1 unreliable sources | resilient fetch + circuit breaker + source_health | `packages/tip_http`, `packages/tip_source_health` |
| TP2 corroboration | canonical normalisation | `packages/tip_schemas/indicators.py` |
| TP3 lookup latency | Redis hot path | `services/ioc-collector` |
| TP4 connection limits | PgBouncer transaction pooling | `infra/pgbouncer`, `packages/tip_db` |
| TP5 AI off hot path | LiteLLM isolation | `packages/tip_ai`, `infra/litellm` |
| TP6 AI quota | smart picker + serialised legs + cache-first | `services/*/routes/*analyze*`, `infra/litellm/config.yaml` |
| TP7 schema isolation | schema-per-service, no cross-FK | `services/*/app/models.py` |
| TP8 secret bootstrap | shared bootstrap token | `services/secrets` |
| TP9 migration | one-shot alembic-init | `infra/alembic-init` |
| TP10 frontend fan-out | BFF proxy | `frontend/src/app/api/[...path]/route.ts` |
