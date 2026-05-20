# Engineering Choices

This document records the cross-cutting engineering decisions that shape
every service. Per-library rationale (FastAPI vs Flask, etc.) is in
`12_technology_choices/`; this document covers the *structural* choices.

## EC1 — Monorepo with path-installed shared packages

**Choice:** one repository; nine shared libraries under `packages/`
installed into each service via path dependencies
(`tip-common = { path = "../../packages/tip_common" }`).

**Why:** every service needs the same logging, settings, error handling,
DB session factory, cache wrapper, resilient HTTP client, and auth
middleware. Duplicating these would guarantee drift. A shared library set
gives one implementation, one place to fix a bug.

**Why path deps and not a published package index:** each service's
Dockerfile gets a clean, independent build with layer caching per
service. There is no internal PyPI to operate. The tradeoff — a change to
a shared package rebuilds every dependent service — is acceptable for a
single-team monorepo.

## EC2 — `create_service_app` factory

**Choice:** every service builds its FastAPI app through one factory in
`tip_common` that wires logging, correlation-ID middleware, error
handlers, and lifespan hooks identically.

**Why:** consistency. A reader who learns one service's `main.py` can read
any other's. Cross-cutting concerns (structured JSON logs, correlation
IDs) are enforced centrally, not re-implemented 15 times.

## EC3 — Async everywhere

**Choice:** every service is async (FastAPI + asyncpg + httpx async).

**Why:** the workload is I/O-bound — external HTTP fetches, database
round-trips, AI calls. Async lets one worker handle many concurrent
in-flight I/O operations without thread overhead. The ingest cycles'
`asyncio.gather` parallelism (G2) depends on this.

**Tradeoff:** one sync island remains — APScheduler 3.x requires a sync
`SQLAlchemyJobStore`, so the `scheduler` service runs a small sync engine
(psycopg2) alongside the async one. This is documented as a known wart.

## EC4 — Schema-per-service, one database

**Choice:** one Postgres database `tip`, fifteen schemas, no cross-schema
foreign keys.

**Why:** isolation (G5) without the operational cost of fifteen
databases. PgBouncer multiplexes connections. Cross-service relations use
stable external IDs.

**Tradeoff:** no database-level referential integrity across services —
the application is responsible for keeping cross-service references valid.
This is the price of independent deployability.

## EC5 — PgBouncer in transaction-pooling mode

**Choice:** all services connect to PgBouncer (6432), not Postgres
directly; transaction pooling; `statement_cache_size=0` on asyncpg.

**Why:** 15 services × pool size would exhaust Postgres connections.
Transaction pooling multiplexes many client connections onto few server
ones. Prepared statements are disabled because transaction pooling
forbids them.

## EC6 — LiteLLM proxy as the single AI boundary

**Choice:** all AI calls route through one LiteLLM proxy container;
services hold only the proxy master key; the proxy holds provider keys
and the fallback config.

**Why:** one egress boundary to audit (SC5), one place to rotate keys,
one place to change providers, provider-SDK churn isolated from services.

**Tradeoff:** the proxy is a shared dependency; if it is down, all AI is
down (but the platform keeps serving stored data — G3).

## EC7 — Cache-first AI insights, versioned by prompt

**Choice:** every AI insight is persisted with a `prompt_version`;
re-requesting returns the saved row unless `force=true`.

**Why:** AI provider quota is scarce (TP6). An analyst re-opening a threat
must not re-bill the model. Bumping `prompt_version` invalidates caches
platform-wide when prompts change.

## EC8 — Resilient HTTP as a library, not a pattern

**Choice:** `tip_http.fetch_with_resilience` is a function every ingester
calls, not a convention each re-implements.

**Why:** uniform timeout/retry/circuit-breaker behaviour; uniform
`source_health` updates; one place to tune backoff.

## EC9 — Edge auth, trusted internal network

**Choice (commit `5d216c1`):** auth enforced at browser↔BFF; data
services run `DISABLE_AUTH=true`.

**Why:** removes a whole class of inter-service auth failures (the
24-hour 401 cascade, OC5) at the cost of treating the docker network as a
trust boundary — acceptable because no data-service port is externally
exposed.

## EC10 — Background work via FastAPI BackgroundTasks

**Choice:** post-response work (KEV backfill, async investigation) uses
FastAPI `BackgroundTasks`, not bare `asyncio.create_task`.

**Why:** `BackgroundTasks` holds a strong reference so the coroutine is
not garbage-collected mid-run. The bare-`create_task` approach was tried
and silently stopped after the response returned (OC8).

## EC11 — Per-resource `analyze` endpoints with serialised AI legs

**Choice:** threat / actor insight generation runs its 2–3 AI legs
(IOC extraction, hunting hypothesis, flowviz) serially, not in parallel.

**Why:** GitHub Models caps concurrent requests per key (1 for
`gpt-5-chat`, 2 for `gpt-4o`). Parallel legs trip the cap; serial legs
never do, regardless of which model the smart-picker landed on (TP6,
commit `61ba20a`).

## EC12 — Auto-promotion with the analyst as the gate

**Choice:** AI-extracted IOCs are auto-promoted into the central IOC
library (tagged `from-threat-insight` / `from-actor-insight`) but are
**not** auto-pushed to the firewall.

**Why:** the analyst reviews before action. The platform reduces manual
copying (promotion) without removing human judgement (action).

## Decision traceability

Every choice here is observable in the code:

| Choice | Observable at |
|---|---|
| EC1 monorepo | `services/*/pyproject.toml` path deps |
| EC2 factory | `packages/tip_common` `create_service_app` |
| EC3 async | every `services/*/app/main.py` |
| EC4 schema-per-service | `services/*/app/models.py` `SCHEMA=` |
| EC5 PgBouncer | `infra/pgbouncer/`, `packages/tip_db` |
| EC6 LiteLLM | `infra/litellm/`, `packages/tip_ai/factory.py` |
| EC7 cache-first | `services/threat-intel/app/routes/threats.py` analyze |
| EC8 resilient HTTP | `packages/tip_http` |
| EC9 edge auth | `infra/docker-compose.yml` `DISABLE_AUTH` |
| EC10 BackgroundTasks | `services/vuln-intel/app/routes/refresh.py` |
| EC11 serial legs | `services/threat-intel/app/routes/threats.py` |
| EC12 auto-promote | `services/threat-actors/app/routes/actors.py` |
