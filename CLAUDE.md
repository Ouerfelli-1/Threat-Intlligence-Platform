# TIP Platform

Threat Intelligence Platform for a finance-sector enterprise. 15 backend microservices (Python/FastAPI), one Postgres DB (schema per service) via PgBouncer, Redis for caching, OpenRouter for AI synthesis. Spec lives in `prompt/prompt.md`. Implementation plan: `C:\Users\moham\.claude\plans\tip-platform-lovely-ocean.md`.

## Repository layout

```
services/        15 FastAPI services
packages/        9 shared libraries (uv path deps)
infra/           docker-compose + alembic-init + bootstrap scripts
prompt/          spec (untouched) + credentials.env
AvailableServices/   legacy code being refactored into flowviz / asm / domainwatch
```

## Local dev

```bash
# 1. one-time setup
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # → FERNET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"                                # → SECRETS_BOOTSTRAP_TOKEN
docker compose -f infra/docker-compose.yml up -d postgres pgbouncer redis
python infra/bootstrap/seed_secrets.py        # seeds RS256 keypair, per-service bootstrap tokens, credentials.env

# 2. run the platform (dev overlay = bind-mounts packages, DISABLE_AUTH=true)
docker compose -f infra/docker-compose.yml --env-file .env -f infra/docker-compose.dev.yml up -d
# or simply: make up  (Makefile passes --env-file automatically)

# 3. verify
python infra/bootstrap/smoke_test.py
```

## Cross-cutting invariants

- **No service touches another's DB tables.** Cross-service data flow is API-only.
- **No FK across schemas.** Services key by stable IDs (CVE-ID, MITRE technique ID, normalized indicator value).
- **AI reads processed data only.** Ingestion jobs never call the LLM.
- **One Postgres database, one schema per service.** All connections go through PgBouncer (port 6432, transaction pooling).
- **Every external source call** goes through `tip_http.fetch_with_resilience` for timeout, retry, circuit breaker.
- **Confidence scores** are computed per-data-type (`tip_schemas.confidence`); stored with the inputs that produced them.
- **Secrets** live in the `secrets` service, fetched at startup; only `FERNET_KEY` and `SECRETS_BOOTSTRAP_TOKEN` stay in `.env`.
- **Service JWTs** are minted by `auth` (`/service-login`); used for all inter-service calls. `DISABLE_AUTH=true` bypasses validation in dev; refused if `TIP_ENV=production`.

## Shared packages

| Package | Purpose |
|---|---|
| `tip_common` | Settings, logging, errors, correlation IDs, `create_service_app` factory |
| `tip_auth` | RS256 JWT middleware + `require_permission` dependency |
| `tip_secrets` | Client to the `secrets` service; in-memory cache, bootstrap-aware |
| `tip_db` | Async SQLAlchemy base + session factory (asyncpg through PgBouncer) |
| `tip_cache` | Redis async wrapper (JSON helpers, incr-with-ttl) |
| `tip_http` | httpx wrapper + `fetch_with_resilience` (retry, circuit breaker, timeout) |
| `tip_source_health` | `SourceHealthRepository` class + per-service `source_health` table builder |
| `tip_schemas` | Indicator normalization, confidence config, `AIInsight` schema |
| `tip_ai` | OpenRouter client, `ContextProvider` protocol, `generate_insight()` |

## Service catalog

(Per-service rows are filled in as each service ships.)

| Service | Port | Schema | Key details |
|---|---|---|---|
| auth | 8000 | `auth` | RS256 JWT issuer; seeds roles, service accounts, admin user at startup; bootstrap dance with secrets |
| news-collector | 8001 | `news` | RSS/Atom ingest + article AI insights; dedup by SHA256(canonicalized URL) |
| vuln-intel | 8002 | `vuln` | NVD CVE 2.0 API, EPSS, CISA KEV; CVE AI insights |
| threat-intel | 8003 | `threat` | Supply-chain RSS feeds, HIBP domain breach lookup |
| ioc-collector | 8004 | `ioc` | ThreatFox + MalBazaar + OTX; corroboration counting; Redis hot-path lookup |
| threat-actors | 8005 | `actors` | MITRE ATT&CK STIX bundles + ransomware.live; actor AI insights |
| integrations | 8006 | `integrations` | Wazuh JWT auth + sync; MISP pull + selective push (confidence ≥ 0.85) |
| cmdb | 8007 | `cmdb` | Asset CRUD + versioned org profile; required by orchestrator + HIBP |
| flowviz | 8008 | `flowviz` | Prompts ported verbatim from directFlowPrompts.ts; cached by sha256(input+PROMPT_VERSION) |
| asm | 8009 | `asm` | Passive-only: crt.sh, HackerTarget, Wayback, AnubisDB, URLScan; active brute-force removed |
| domainwatch | 8010 | `domainwatch` | Playwright screenshots (mcr.microsoft.com/playwright/python base image); DNS in ThreadPoolExecutor |
| scheduler | 8011 | `scheduler` | APScheduler 3.x; psycopg2 sync job store; 12 built-in jobs + 60s watchdog |
| secrets | 8012 | `secrets` | Fernet-encrypted vault; bootstrap endpoint supports single-secret and bulk modes |
| indicator-intel | 8013 | `indicator` | Parallel passive sources (ip-api, Shodan, crt.sh, WHOIS, IOC DB, actors, articles, IntelOwl); AI verdict |
| orchestrator | 8014 | `orchestrator` | 4-step AI cycle (CVE relevance → actor likelihood → correlation → brief); geo prediction; /ask |

## Bootstrap order (first deploy)

1. Postgres, PgBouncer, Redis come up.
2. `alembic-init` runs all per-service migrations, then exits.
3. `secrets` starts (uses `FERNET_KEY`, validates `SECRETS_BOOTSTRAP_TOKEN`).
4. `infra/bootstrap/seed_secrets.py` is run (creates RS256 keypair, per-service bootstrap tokens, seeds `credentials.env`).
5. `auth` starts, calls `POST secrets/internal/bootstrap-fetch` for its RS256 keys.
6. Every other service starts, fetches its own `SVC_<NAME>_BOOTSTRAP_TOKEN`, then `POST auth/service-login` to get a service JWT.

Until `auth` and `secrets` ship, run with `DISABLE_AUTH=true` and read secrets directly from env where needed.

## Per-service notes

### auth (8000, schema `auth`)
**Purpose.** JWT issuance, RBAC, sessions, service identity.
**Env vars always-on.** `DATABASE_URL`, `REDIS_URL`, `SECRETS_URL`, `SECRETS_BOOTSTRAP_TOKEN`, `BOOTSTRAP_ADMIN_USERNAME`, `BOOTSTRAP_ADMIN_PASSWORD`.
**Startup.** Calls `POST secrets/internal/bootstrap-fetch` to get RS256 keypair, then seeds roles + service accounts + admin user.
**Non-obvious.** The auth service does NOT use `tip_auth` middleware — it validates its own JWTs locally via `app/deps.py`. Service accounts store `bootstrap_token_hash`; `seed_secrets.py` must write both to secrets and to `auth.service_accounts`.

### news-collector (8001, schema `news`)
**Purpose.** RSS/Atom feed ingestion + article AI insights.
**Secrets fetched.** `OPENROUTER_API_KEY`.
**Scheduler trigger.** `POST /ingest/run` every 2h.
**Non-obvious.** Dedup by SHA256 of canonicalized URL. HTML→text via `readability-lxml`. Tags from feed categories + keyword heuristic.

### vuln-intel (8002, schema `vuln`)
**Purpose.** NVD CVE 2.0 API, EPSS, CISA KEV ingestion + CVE AI insights.
**Secrets fetched.** `NVD_API_KEY` (optional).
**Scheduler triggers.** `POST /refresh/nvd` every 6h; `/refresh/kev` daily 06:00; `/refresh/epss` daily 06:30.
**Non-obvious.** Incremental NVD pull by `lastModified` window. EPSS is a full daily snapshot (all rows replaced).

### threat-intel (8003, schema `threat`)
**Purpose.** Supply-chain advisories (RSS), HIBP domain breach lookup.
**Secrets fetched.** `HIBP_API_KEY` (optional).
**Scheduler trigger.** `POST /ingest/run` every 4h.
**Non-obvious.** HIBP reads `public_domains` from CMDB `/profile/latest` at each cycle.

### ioc-collector (8004, schema `ioc`)
**Purpose.** ThreatFox, MalBazaar, OTX IOC ingestion with corroboration scoring.
**Secrets fetched.** `ABUSECH_API_KEY`, `OTX_API_KEY` (optional).
**Scheduler trigger.** `POST /ingest/run` every 3h.
**Non-obvious.** `POST /indicators/lookup` is the hot path — checks Redis first (`ioc:<type>:<value>`, 10m TTL).

### threat-actors (8005, schema `actors`)
**Purpose.** MITRE ATT&CK STIX bundles, ransomware.live groups+victims, actor AI insights.
**Scheduler trigger.** `POST /refresh` daily 03:00.
**Non-obvious.** STIX processing order: tools/malware → actors → relationships (tool/actor maps built for FK resolution).

### integrations (8006, schema `integrations`)
**Purpose.** Wazuh SIEM + MISP sharing platform integration.
**Secrets fetched.** `WAZUH_URL`, `WAZUH_USERNAME`, `WAZUH_PASSWORD`, `MISP_URL`, `MISP_API_KEY`, `MISP_PUSH_EVENT_ID`.
**Scheduler trigger.** `POST /wazuh/sync` every 30min (MISP sync included).
**Non-obvious.** Wazuh JWT cached 1h in memory; invalidated on 401. MISP push targets a single event ID; only IOCs with confidence ≥ 0.85 not already in `misp_pushes`.

### cmdb (8007, schema `cmdb`)
**Purpose.** Asset inventory CRUD + versioned company profile (required by orchestrator + HIBP).
**Non-obvious.** Every `PATCH /profile` writes a new version row; history available via `/profile/versions`.

### flowviz (8008, schema `flowviz`)
**Purpose.** Threat description → attack flow JSON (ATT&CK chain).
**Secrets fetched.** `OPENROUTER_API_KEY`.
**Non-obvious.** Cache key = `sha256(input_text + PROMPT_VERSION)`. Prompts ported verbatim from `AvailableServices/Flowviz/flowviz-main/src/features/flow-analysis/services/directFlowPrompts.ts`. Active brute-force methods from ASM were removed; passive methods kept.

### asm (8009, schema `asm`)
**Purpose.** Passive attack surface discovery (cert transparency, passive DNS, Shodan).
**Secrets fetched.** `SHODAN_API_KEY` (optional).
**Scheduler trigger.** `POST /scan/run` daily 02:00.
**Non-obvious.** Active methods (nmap, wordlist DNS brute-force) intentionally deleted. Passive sources: crt.sh, HackerTarget, Wayback Machine, AnubisDB, URLScan.

### domainwatch (8010, schema `domainwatch`)
**Purpose.** Periodic domain monitoring: DNS, content hash, screenshot, IOC lookup.
**Base image.** `mcr.microsoft.com/playwright/python:v1.46.0-jammy` (ships browser binaries).
**Scheduler trigger.** `POST /check/run` every 12h.
**Non-obvious.** DNS calls run in `ThreadPoolExecutor` to avoid blocking the async loop. Screenshots stored on disk at `/var/lib/domainwatch/screenshots/` (volume-mounted); DB stores path only.

### scheduler (8011, schema `scheduler`)
**Purpose.** Single owner of all recurring jobs.
**Non-obvious.** APScheduler 3.x `SQLAlchemyJobStore` requires psycopg2 sync URL. `Settings.sync_db_url` property derives it automatically. 12 built-in jobs registered with `replace_existing=True`. Watchdog sweep every 60s marks stale `running` rows as `timeout`.

### secrets (8012, schema `secrets`)
**Purpose.** Fernet-encrypted credential vault.
**Env vars always-on.** `FERNET_KEY` (required; service refuses to start without it), `SECRETS_BOOTSTRAP_TOKEN`.
**Non-obvious.** `/internal/bootstrap-fetch`: if `secret_name` provided → returns `{"value": "..."}` (single-secret mode used by `SecretsClient`); if absent → returns `{"secrets": {RS256_PRIVATE_KEY, RS256_PUBLIC_KEY}}` (bulk mode for auth service only).

### indicator-intel (8013, schema `indicator`)
**Purpose.** AI-driven passive investigation of IPs and domains.
**Secrets fetched.** `OPENROUTER_API_KEY`, `SHODAN_API_KEY`, `INTELOWL_URL`, `INTELOWL_API_KEY`.
**Non-obvious.** All sources run with `asyncio.gather(..., return_exceptions=True)` — partial failure is normal. Sync path caps at 30s; deep investigations use `/investigate/async`. WHOIS calls run in `ThreadPoolExecutor`.

### orchestrator (8014, schema `orchestrator`)
**Purpose.** AI brain — 4-step analysis cycle, geo prediction, ad-hoc /ask.
**Secrets fetched.** `OPENROUTER_API_KEY`.
**Scheduler triggers.** `POST /analyze` every 6h; `POST /analyze/geo` daily 05:00.
**Non-obvious.** 4 steps run sequentially (each builds on prior). Failed step is logged and skipped; cycle continues. Top-3 brief findings each get a flowviz attack flow embedded in the report. Orchestrator is the ONLY service that fans out to multiple other service APIs.

## Where to change behavior

- **Cron schedules** — `services/scheduler/app/jobs.py` (declarative registration with `replace_existing=True`).
- **Confidence weights** — `packages/tip_schemas/src/tip_schemas/confidence.py` (`CONFIGS`, `SOURCE_RELIABILITY`).
- **AI prompts** — per-service `app/prompts.py` files. Versioned via `prompt_version` saved with each output.
- **External source list per service** — per-service `app/sources.py`.
- **Auth permissions** — seeded by `auth` service at startup; runtime CRUD via `/roles` admin API.

## Useful commands

```bash
make up                            # docker compose up -d
make down                          # docker compose down
make logs svc=news-collector       # tail logs for a service
make psql                          # psql shell inside the container
make smoke-test                    # /health probe all 15 services
make migrate                       # run alembic-init container (no-op if up to date)
```
