# Scope

## Functional scope

The platform's responsibility chain, end to end:

1. **Ingest** — pull from external sources on a schedule (`scheduler`
   service fires every 2–12 hours per source).
2. **Normalise** — convert raw feed entries into typed rows
   (`tip_schemas.indicators.normalize` + per-service schema mapping).
3. **Persist** — store in per-service Postgres schemas behind PgBouncer.
4. **Score** — compute a confidence value using `tip_schemas.confidence`
   weighted per `DataType`.
5. **Enrich** — corroborate across sources by normalised value; for IOCs
   write `indicator_sources` rows.
6. **Analyse** — orchestrator's 4-step AI cycle (CVE relevance →
   actor likelihood → correlation → executive brief).
7. **Distribute** — UI rendering, optional SMTP notifications, optional
   MISP push.
8. **Investigate** — analyst-initiated deep investigation
   (`indicator-intel`) of single artefacts.

## Service boundaries inside the scope

15 services, each owns a single schema:

| Service | Schema | Port | Responsibility (one sentence) |
|---|---|---|---|
| auth | `auth` | 8000 | Issues RS256 JWTs; user/role/session CRUD |
| news-collector | `news` | 8001 | RSS / Atom ingest + per-article AI insights |
| vuln-intel | `vuln` | 8002 | NVD CVE 2.0, EPSS, CISA KEV ingest + backfill |
| threat-intel | `threat` | 8003 | Supply-chain advisories, HIBP, threat-level AI insight |
| ioc-collector | `ioc` | 8004 | ThreatFox / MalBazaar / OTX with corroboration scoring |
| threat-actors | `actors` | 8005 | MITRE ATT&CK actors, ransomware groups + AI insight |
| integrations | `integrations` | 8006 | Wazuh SIEM, MISP push/pull |
| cmdb | `cmdb` | 8007 | Asset inventory + versioned company profile |
| flowviz | `flowviz` | 8008 | Threat → ATT&CK attack-flow graph generator |
| asm | `asm` | 8009 | Passive attack-surface discovery (cert transparency, passive DNS, Shodan) |
| domainwatch | `domainwatch` | 8010 | Periodic domain monitoring with Playwright screenshots |
| scheduler | `scheduler` | 8011 | APScheduler central trigger for every cron job |
| secrets | `secrets` | 8012 | Fernet-encrypted credential vault |
| indicator-intel | `indicator` | 8013 | AI-driven passive investigation + Google dorking |
| orchestrator | `orchestrator` | 8014 | 4-step AI cycle, geo prediction, ad-hoc /ask, notifications |

Plus three infrastructure containers and two operational sidecars:

- `postgres` — single Postgres instance, all 15 schemas
- `pgbouncer` — transaction-pooling connection multiplexer (port 6432)
- `redis` — cache + circuit-breaker state
- `litellm` — AI gateway (proxy mode, port 4000)
- `alembic-init` — one-shot migration runner
- `bootstrap-seed` — one-shot data-seeder for the company profile + tags
- `frontend` — Next.js 16 SSR + BFF proxy (port 3000)

The frontend is the only service the end user accesses directly.

## Out of scope

Already enumerated in `objectives.md` "Explicit non-goals". Reiterating
the most consequential exclusions:

- **No active scanning.** ASM is read-only against the public web.
- **No multi-tenant model.** One organisation per deployment.
- **No Kubernetes / no managed cloud.** Single-host Docker Compose.
- **No real-time event bus.** Ingest is cyclical batch with seconds-level
  latency from "event happened at upstream" to "row visible in TIP".

## Data scope

The platform stores:

- **Structured threat intelligence** (CVEs, IOCs, actor profiles,
  ransomware victims, threat events) — bulk of the database.
- **Per-resource AI insight payloads** as JSONB blobs versioned by
  `prompt_version` (`news.article_insights`, `vuln.cve_insights`,
  `threat.threat_insights`, `actors.actor_insights`).
- **Analyst notes** per-resource (`*_notes` tables under each schema).
- **Audit trails** — `auth.audit_log`, `secrets.access_log`,
  `orchestrator.notification_dispatches`, `scheduler.job_run_history`.
- **Company profile versions** — one row per `PATCH /profile`
  (`cmdb.org_profile_versions`).
- **Dork-run history** — `indicator.dork_runs` + `indicator.dork_findings`.

The platform does **not** store:

- Bank customer PII.
- Live network packets / pcaps.
- Email content (only HIBP breach references).
- Source code from monitored repositories (only dork search hit
  metadata).

## Operational scope

The platform's operator owns:

- The Docker host (Linux server, ≥ 8 GB RAM, ≥ 40 GB SSD).
- The `.env` file (`FERNET_KEY`, `POSTGRES_PASSWORD`,
  `SECRETS_BOOTSTRAP_TOKEN`, `BOOTSTRAP_ADMIN_PASSWORD`).
- The contents of the secrets vault (provider keys, SMTP creds, optional
  Google CSE keys).
- Backups (the host's `postgres-data` and `domainwatch-screenshots`
  named volumes).

The platform does **not** auto-manage:

- TLS termination (a reverse proxy should sit in front in production).
- DNS, certificate rotation, OS-level patching.
- Postgres minor-version upgrades.
- LiteLLM proxy upgrades (manual `docker pull` + `make up`).
