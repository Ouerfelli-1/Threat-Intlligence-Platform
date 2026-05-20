# Design Goals

The design is governed by a small set of explicit goals. Each goal is
stated, justified, and traced to the mechanism that enforces it.

## G1 — Availability over consistency for intelligence reads

**Goal:** read APIs always serve the latest *stored* data; they never
block waiting on a live external fetch.

**Justification:** an analyst mid-incident needs an answer now, even if it
is five minutes stale, more than a perfectly fresh answer in thirty
seconds.

**Mechanism:** ingest is decoupled from read. Reads hit Postgres/Redis;
fetches happen on the scheduler's cycle. "Stale over blocking" is a stated
invariant in `CLAUDE.md`.

## G2 — Partial success is success

**Goal:** an ingest cycle that gets 3 of 5 sources is a successful cycle.

**Justification:** external sources fail independently and often; an
all-or-nothing cycle would rarely complete.

**Mechanism:** `asyncio.gather(*tasks, return_exceptions=True)` in every
ingester; failed sources logged to `source_health`, not raised.

## G3 — AI degrades, never breaks

**Goal:** AI provider failure degrades one feature (one insight), not the
platform.

**Justification:** the LLM is the least reliable dependency (quota,
rate-limits, upstream outages). The platform must outlive it.

**Mechanism:** AI isolated behind `tip_ai` + LiteLLM; typed exceptions
handled per-call; cache-first insights; ingesters never import `tip_ai`.

## G4 — One canonical key for cross-source meaning

**Goal:** the same real-world indicator always maps to the same string.

**Justification:** corroboration and cross-service joins are meaningless
otherwise.

**Mechanism:** `tip_schemas.indicators.normalize`, called by every
ingester before persistence; `unique(type, normalized_value)`.

## G5 — Each service owns its data

**Goal:** no service reads another service's tables.

**Justification:** independent deployability and migratability; a schema
change in one service cannot break another's queries.

**Mechanism:** one schema per service, no cross-schema FKs, HTTP-only
cross-service access.

## G6 — Secrets in one place, encrypted, audited

**Goal:** every credential lives in one encrypted store with an access
log; only the master key is outside it.

**Justification:** rotation is a single operation; compliance can audit
who read what.

**Mechanism:** `secrets` service, Fernet-at-rest, `secrets.access_log`;
`.env` holds only `FERNET_KEY` + `SECRETS_BOOTSTRAP_TOKEN`.

## G7 — One command for every operator task

**Goal:** bring-up, migrate, seed, diagnose, and verify are each a single
command.

**Justification:** the bank's IT ops team are not the platform's
developers; they need a small, memorable surface.

**Mechanism:** the `Makefile` — `up`, `down`, `migrate`, `seed`,
`smoke-test`, `check-llm`, `psql`, `logs`.

## G8 — Reproducible builds

**Goal:** the same commit produces the same images and the same running
behaviour.

**Justification:** "works on my machine" is unacceptable for a security
platform a bank depends on.

**Mechanism:** per-service `pyproject.toml` with pinned deps; per-service
Dockerfile; one-shot `alembic-init`; deterministic seed scripts.

## G9 — Latency budget for the hot path

**Goal:** IOC lookup < 200 ms.

**Justification:** Yassine's sub-10-second triage depends on instant
lookups; anything slower drives him back to VirusTotal.

**Mechanism:** Redis-first lookup (`ioc:<type>:<value>`, 10-minute TTL)
with Postgres fallback + cache repopulation.

## G10 — Observable degradation

**Goal:** when something is degraded, an operator can see *what* and *why*
without reading raw logs.

**Justification:** day-2 operations by a non-developer team.

**Mechanism:** `source_health` tables (per source), `job_run_history`
(per scheduled job), `notification_dispatches` (per alert),
`secrets.access_log`, and the two diagnostic scripts.

## Goal interaction and priority

When goals conflict, the resolution order is:

1. **Availability (G1, G2, G3)** beats freshness and completeness.
2. **Isolation (G5, G6)** beats convenience.
3. **Operational simplicity (G7, G8, G10)** beats theoretical scalability.
4. **Latency on the hot path (G9)** is non-negotiable but scoped to one
   endpoint.

This priority order is *why* the platform is single-host Compose rather
than Kubernetes (simplicity beats scale), *why* AI is isolated (avail
beats feature richness), and *why* the IOC lookup has its own Redis path
(one hot path, optimised; everything else, Postgres-direct).
