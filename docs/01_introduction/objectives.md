# Objectives

## Functional objectives

The platform must implement the following capability set, each one
verifiable against a concrete deliverable in the repository.

| # | Objective | Verifying artefact |
|---|---|---|
| F1 | Continuously ingest open-source threat intelligence from heterogeneous feeds | `services/news-collector`, `services/threat-intel`, `services/vuln-intel`, `services/ioc-collector`, `services/threat-actors` |
| F2 | Normalise indicators to a canonical form so cross-source corroboration is meaningful | `packages/tip_schemas/src/tip_schemas/indicators.py` |
| F3 | Score every artefact for confidence using a per-data-type weighting | `packages/tip_schemas/src/tip_schemas/confidence.py` |
| F4 | Provide low-latency IOC lookup (`< 200 ms` Redis hot-path target) | `services/ioc-collector/app/routes/indicators.py` lookup endpoint |
| F5 | Run an AI synthesis layer that **only** reads processed data | `services/orchestrator/`, `packages/tip_ai/` |
| F6 | Produce a daily executive brief and a daily geopolitical outlook | `services/orchestrator/app/analysis.py` `run_analysis_cycle` + `run_geo_prediction` |
| F7 | Generate per-threat / per-actor hunting hypotheses with Wazuh rules and ATT&CK attack-flow graphs | `services/threat-intel/app/routes/threats.py` `/threats/{id}/analyze`; `services/threat-actors/app/routes/actors.py` `/actors/{id}/analyze`; `services/flowviz/` |
| F8 | Perform AI-driven passive investigation of single indicators (IP / domain) | `services/indicator-intel/app/routes/investigations.py` |
| F9 | Google-dorking sub-investigation with Google CSE → DuckDuckGo fallback | `services/indicator-intel/app/dorking/` (added in commit `1cead2e`) |
| F10 | Configurable notifications (SMTP) for the events that matter to the SOC | `services/orchestrator/app/notify/` + `0003_notifications` migration |
| F11 | Asset / company-profile CRUD that the AI uses as relevance context | `services/cmdb/` |
| F12 | RBAC with admin / analyst / viewer roles + per-service permissions | `services/auth/app/seed.py` + `packages/tip_auth/src/tip_auth/middleware.py` |
| F13 | Self-service settings UI for feeds, tags, AI providers, notifications | `frontend/src/app/(app)/settings/page.tsx` |
| F14 | Single-file deployment via `make up` | `infra/docker-compose.yml` + `Makefile` |
| F15 | One-shot smoke test that hits `/health` on all 15 services + LiteLLM | `infra/bootstrap/smoke_test.py` |

## Non-functional objectives

| # | Objective | How it is achieved |
|---|---|---|
| N1 | **Service isolation** — failure of one ingest source does not abort the cycle | `asyncio.gather(..., return_exceptions=True)` across every ingester; per-source `source_health` rows |
| N2 | **Per-data-type confidence scoring** — no single "magic number" | `confidence.py` carries one weight set per `DataType` enum value |
| N3 | **AI never blocks ingest** — provider 429/down keeps platform usable | `tip_ai.LiteLLMClient` errors surface as `LiteLLMRateLimitError` etc., handled per-call |
| N4 | **No inter-service authentication on the docker network** (after commit `5d216c1`) | `DISABLE_AUTH=true` on data services; auth still enforced on the BFF↔browser edge |
| N5 | **Deterministic rebuild** — every service has its own `pyproject.toml` and Dockerfile | 15 self-contained service images |
| N6 | **Database isolation** — one schema per service, no cross-schema FKs | `services/<name>/app/models.py` `SCHEMA = "..."` |
| N7 | **No surprise outbound traffic** — only the LiteLLM proxy and the per-source ingesters talk to the internet | Verified by `egress` review of the compose file |
| N8 | **Reproducible bootstrap** — `make seed && make migrate && make up` brings up an identical stack | Verified by Playwright walkthrough (`screenshots/walkthrough.py`) after a fresh `make clean && make up` |
| N9 | **Operator self-recovery** — `make check-llm` pinpoints the failing link in the AI chain in seconds | `infra/bootstrap/check_litellm.py` |

## Explicit non-goals

The following were deliberately **out of scope** and should not appear in
the evaluation criteria.

- **Active scanning** (Nmap port-scans, brute-force DNS). Removed from
  the ported `asm` service during the refactor (commit history shows
  `engine/modules/nmap_enum.py` deleted).
- **Multi-tenant isolation.** The platform is built for one organisation.
  Multi-tenant evolution is documented but not delivered.
- **Real-time streaming** (Kafka, Kinesis). Ingest is batch-cyclical.
- **Mobile native clients.** The Next.js frontend is responsive but no
  iOS/Android wrappers are shipped.
- **Hot-failover Postgres / multi-region.** Single Postgres instance,
  single Docker host. Backups are an operator responsibility.
- **Custom STIX/TAXII federation.** MISP integration handles the share
  use case for v1.
- **Active blocking / firewall integration.** TIP feeds intelligence;
  the upstream firewall consumes it.

## Success criteria

The platform passes its acceptance test when **all three users** can
perform their daily workflow without touching a tool outside TIP:

| User | Daily workflow that must complete inside TIP |
|---|---|
| Yassine | Paste a suspect IP into `/iocs/lookup`, get a verdict in < 10 s; if "unknown" run `/iocs/investigate` to enrich |
| Amira | Mark new articles relevant / not-relevant; trigger AI insights on three supply-chain threats; review the auto-generated Wazuh rules |
| Karim | Open `/` once, read the Daily Threat Briefing and the Geopolitical Insights card, scan top-ranked actors, leave |

The Playwright walkthrough (`screenshots/walkthrough.py`) demonstrates
that each surface required by these workflows renders correctly against
a freshly-seeded database.
