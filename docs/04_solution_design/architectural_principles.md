# Architectural Principles

The platform is governed by a set of invariants — rules that hold across
every service and are not violated for convenience. They are stated here
as the constitution the rest of the architecture obeys.

## P1 — No service touches another service's database tables

Cross-service data flow is **API-only**. A service may call another
service's HTTP endpoint; it may never `SELECT` from another service's
schema. Enforced by convention and by the schema-per-service layout
(`services/*/app/models.py` each declare a distinct `SCHEMA`).

*Consequence:* services are independently deployable and migratable.

## P2 — No foreign keys across schemas

References between services use stable external identifiers (CVE-ID,
MITRE technique ID, normalised indicator value), never surrogate FKs that
would couple two schemas.

*Consequence:* a service can be split, moved to its own database, or
re-seeded without a platform-wide migration.

## P3 — AI reads processed data only

The AI synthesis layer never reads raw, unprocessed source data and never
sits on the ingest hot path. Ingesters never import `tip_ai`.

*Consequence:* the platform survives AI provider outages (G3); the
prompt-injection blast radius is bounded to a reviewed insight payload.

## P4 — Every external call is resilient

No service calls an external source with a bare `httpx.get`. All outbound
source calls go through `tip_http.fetch_with_resilience` (timeout +
retry + circuit breaker), which also updates `source_health`.

*Consequence:* one slow/failing source degrades gracefully; the cycle
continues (G2).

## P5 — Stale over blocking

Read APIs serve the latest stored data immediately; they never wait on a
live fetch. Freshness is the scheduler's job, not the request's.

*Consequence:* sub-second reads even when upstreams are slow (G1).

## P6 — Confidence is stored with its inputs

Every confidence-scored row persists both the score and the input vector
(`confidence_inputs jsonb`) that produced it.

*Consequence:* the scoring formula can evolve and historical rows can be
re-scored without re-fetching.

## P7 — Secrets live in the vault, encrypted, audited

Only `FERNET_KEY` and `SECRETS_BOOTSTRAP_TOKEN` exist outside the secrets
vault. Every read is logged.

*Consequence:* single-operation rotation; compliance-grade access audit.

## P8 — One schema migration step, ordered before any service

All migrations run from the one-shot `alembic-init` container before any
service starts. Services `depends_on` its successful completion.

*Consequence:* no service ever starts against an un-migrated schema.

## P9 — Confidence/insight outputs are versioned

Every AI output carries a `prompt_version`. Caches key on it.

*Consequence:* prompt changes invalidate caches platform-wide and outputs
remain traceable to the prompt that produced them.

## P10 — The frontend speaks to one origin

The browser only ever calls the frontend origin. All back-end access goes
through the BFF proxy (`frontend/src/app/api/[...path]/route.ts`).

*Consequence:* no CORS sprawl; the internal topology is not exposed to the
browser.

## P11 — Auth at the edge; the docker network is the trust boundary

(Post commit `5d216c1`.) The `auth` service validates JWTs for its own
endpoints; data services trust the private docker network
(`DISABLE_AUTH=true`). No data-service port except the frontend is
externally exposed.

*Consequence:* a whole class of inter-service auth failures is eliminated;
the security model depends on the host's network isolation.

## P12 — Idempotent, observable background work

Long-running post-response work uses FastAPI `BackgroundTasks`; it is
idempotent (upsert-based) and observable (writes audit/health rows).

*Consequence:* background work survives the request, can be retried
safely, and its outcome is inspectable.

## Principle conflicts and their resolution

These principles occasionally pull against each other. The resolutions:

| Tension | Resolution | Principle that wins |
|---|---|---|
| Isolation (P1/P2) vs. join-ability | Stable external IDs + HTTP fan-out | P1/P2 — isolation wins; the orchestrator does the joining at the application layer |
| Freshness vs. availability | Serve stored data; fetch on schedule | P5 — availability wins |
| Defence-in-depth auth vs. operational reliability | Edge auth + trusted network | P11 — reliability wins, scoped by network isolation |
| AI richness vs. survivability | AI isolated, off hot path | P3 — survivability wins |

## How the principles are kept honest

- **Code review** against this list.
- **Structural enforcement** where possible — e.g. P3 is enforced by the
  *absence* of a `tip_ai` import in `sources/`, not by a comment.
- **The documentation** — every per-service doc in `06_services/` notes
  which principles the service exemplifies and any deviations (e.g. the
  scheduler's sync-engine wart deviating from "async everywhere").
