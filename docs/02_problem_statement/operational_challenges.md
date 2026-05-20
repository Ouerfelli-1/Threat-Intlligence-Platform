# Operational Challenges

Operating a 15-service platform on a single host introduces challenges
distinct from the design-time technical problems. This document covers the
runtime / day-2 concerns and how the platform addresses each.

## OC1 — Bring-up ordering

Fifteen services plus three infrastructure containers plus two one-shot
sidecars have a strict dependency order:

1. `postgres`, `pgbouncer`, `redis` (healthy)
2. `alembic-init` (runs every migration, exits 0)
3. `secrets` (needs `FERNET_KEY`)
4. `seed_secrets.py` (operator-run; populates the vault)
5. `litellm` (pulls provider keys from the vault)
6. `auth` (fetches RS256 keys from the vault)
7. every other service (fetches its own credentials, then serves)
8. `bootstrap-seed` (seeds company profile + tags)
9. `frontend`

**Addressed by:** Compose `depends_on` with `condition:
service_healthy` / `service_completed_successfully`, plus health-checks
on `postgres`, `pgbouncer`, `redis`, `litellm`, `auth`. The full ordering
is documented in `CLAUDE.md` "Bootstrap order".

## OC2 — Diagnosing "the AI doesn't work"

The AI request chain has six links (env → secrets reachable → vault has
master key → proxy reachable → proxy accepts key → upstream provider
responds). A failure anywhere produces the same user-visible symptom.

**Addressed by:** `infra/bootstrap/check_litellm.py` (run via
`make check-llm`) walks the chain in order and stops at the first failing
link, printing exactly which step broke and the most likely fix. This
turns a four-log investigation into one command.

## OC3 — Diagnosing "a service is down"

**Addressed by:** `infra/bootstrap/smoke_test.py` (run via
`make smoke-test`) probes `/health` on all 15 services and the LiteLLM
proxy concurrently, printing an `[OK]` / `[BAD]` table.

## OC4 — AI provider quota exhaustion mid-day

GitHub Models' daily per-model quota can be exhausted by active analyst
use. When that happens, AI insight generation fails silently if not
handled.

**Addressed by:** (1) the smart-model picker prefers the
largest-quota model; (2) the LiteLLM proxy fallback cascade tries other
models in the same provider; (3) insights are cache-first so re-opens
don't burn quota; (4) failures persist a dispatch/insight row with the
exact error string (`"Rate limit of 12 per 86400s ..."`) so the operator
sees the cause rather than an empty result. This was a real incident
resolved in commit `61ba20a`.

## OC5 — Service JWT expiry causing silent inter-service 401 cascade

Originally every service authenticated inter-service calls with a 24-hour
service JWT. When the scheduler's cached JWT was never attached to its
outbound calls, **every scheduled ingest silently 401'd for ~24 hours**
(real incident, commit `5bd8b73`).

**Addressed by:** first a targeted fix (attach the JWT + self-heal on
401), then the broader architectural simplification (commit `5d216c1`):
data services run `DISABLE_AUTH=true` and trust the docker network, so
inter-service calls cannot 401 at all. Auth remains enforced only at the
browser↔BFF edge.

## OC6 — Stale-token user lockout

When a user's session expired or was revoked, the SPA could enter a
redirect loop or spam "missing bearer token" toasts.

**Addressed by:** `frontend/src/lib/api.ts` single-flight redirect — a
401 clears auth once and redirects to `/login` exactly once; pre-auth
paths (`/login`, `/refresh`) bypass the token guard (commit `035ccfc`).

## OC7 — Schema drift between KEV and CVE tables

The "exploited only" CVE filter is an inner join `CVE ⋈ KEV`. The
incremental NVD pull only fetches a recent `lastModified` window, so KEV
entries referencing older CVEs (Heartbleed, Log4Shell) had no matching
CVE row and were silently dropped — the filter returned ~12 instead of
~1500 (real incident, commit `e2443dd`).

**Addressed by:** a `POST /refresh/kev-backfill` endpoint that fetches
each missing CVE individually from NVD's `?cveId=` API; and
`POST /refresh/kev` now auto-fires the backfill for any newly-discovered
KEV CVE so the drift cannot reopen.

## OC8 — Long-running background work surviving the request

Several operations (KEV backfill, async investigation) outlive their HTTP
request. A bare `asyncio.create_task` gets garbage-collected mid-run.

**Addressed by:** FastAPI `BackgroundTasks` (which holds a strong
reference), used for the KEV backfill (commit `e2443dd`). This was found
the hard way — the first attempt with `asyncio.create_task` silently
stopped after the response returned.

## OC9 — Playwright in a container

The `domainwatch` service needs a real browser for screenshots, which is
heavy to install.

**Addressed by:** `domainwatch` uses the
`mcr.microsoft.com/playwright/python` base image which ships the browser
binaries, avoiding a fragile runtime `playwright install`.

## OC10 — Reproducible UI verification

After UI changes, manually clicking 40 surfaces to confirm nothing broke
is slow and error-prone.

**Addressed by:** `screenshots/walkthrough.py` — a Playwright script that
logs in and captures all 40 surfaces in one run, doubling as a smoke test
and a report-figure generator.

## Operational runbook index

| Symptom | Command | Document |
|---|---|---|
| Stack won't come up | `make up` then `make smoke-test` | `09_devops/orchestration.md` |
| AI returns nothing | `make check-llm` | `09_devops/observability.md` |
| Service unreachable | `make smoke-test` | `09_devops/monitoring.md` |
| Exploited-CVE filter empty | `POST /refresh/kev-backfill` | `06_services/vuln_intel/overview.md` |
| Need DB shell | `make psql` | `07_database/migrations.md` |
| UI regression check | `python screenshots/walkthrough.py` | `11_testing/playwright_testing.md` |
