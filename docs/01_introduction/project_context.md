# Project Context

## What this project is

A **Threat Intelligence Platform (TIP)** built for a single, concrete
customer profile: a 500 – 1 000-person **finance-sector enterprise in North
Africa** whose SOC team is presently coordinating across ten or more
disconnected tools (RSS feeds, CVE databases, ransomware victim lists,
VirusTotal, Wazuh dashboards, MISP instances, and spreadsheet IOC lists).

The platform is **not** a general-purpose product. The product
specification at `prompt/prompt.md` defines three users by name with
distinct workflows:

| User | Role | Primary need |
|---|---|---|
| Yassine | SOC Analyst | Fast IOC lookups (target < 10 s), alert triage |
| Amira | TI Analyst | Owns the intelligence library; manages actors, writes briefs |
| Karim | Security Manager | Reads one daily executive brief; makes go/no-go decisions |

Every design decision in the repository (cache TTLs, default sort orders,
endpoint shapes, AI prompt structure) traces back to one of these three
workflows.

## What is inside the repository

```
PFE-TIP/
├── services/             15 FastAPI back-end services
├── packages/             9 shared Python libraries (path-installed)
├── frontend/             Next.js 16 App Router single-page app
├── infra/                docker-compose, alembic init container, bootstrap
│                         scripts, LiteLLM proxy, PgBouncer config
├── prompt/               product spec + initial credentials + customer profile
├── OpenAPI/              auto-extracted OpenAPI documents per service
├── screenshots/          Playwright walkthrough output (40 PNGs)
└── CLAUDE.md             operational playbook
```

The repository is a **monorepo** because every service shares the same
shared package set (`tip_common`, `tip_auth`, `tip_db`, `tip_cache`,
`tip_http`, `tip_secrets`, `tip_schemas`, `tip_source_health`, `tip_ai`)
and the same deployment unit (`infra/docker-compose.yml`).

## Operational mode

The platform is deployed to a **single Linux host** (Docker Compose,
not Kubernetes). Inside the host every service is a container on a private
Docker bridge network. Only the frontend (port 3000) and select diagnostic
ports (auth `8000`, scheduler `8011`) are exposed.

This is intentional: a 1 000-person bank does not need horizontal pod
auto-scaling on day one. Compose ships fast, reproduces exactly, and
gives the operator a single `make up` command. A Kubernetes evolution
path is documented in `16_future_work/infrastructure_improvements.md`.

## Operating window

The platform is designed to **run continuously**. Scheduled ingest jobs
fire every 2–12 hours per source (configured in
`services/scheduler/app/jobs.py`). The orchestrator's full AI analysis
cycle runs every 6 hours and the geopolitical prediction once a day at
05:00 UTC.

When external sources fail (network, API quota), the platform must
**continue to serve cached intelligence**. This is enforced by
`packages/tip_http/fetch_with_resilience.py` and per-service
`source_health` tables.

## Why this is being built

Two combined pressures justified building rather than buying:

1. **Regional adversary coverage.** Commercial TIPs cover global APT
   activity well but treat North-African finance-sector targeting as a
   long-tail concern. The team needed a platform that could be
   prompt-tuned (`services/orchestrator/app/prompts.py`) to weigh MENA
   campaigns and SWIFT/payment-system targeting more heavily.

2. **Data sovereignty.** Financial regulators in the region restrict the
   off-premises movement of customer-adjacent data. A self-hosted
   platform where the AI gateway (LiteLLM proxy at `infra/litellm/`) is
   the *only* outbound boundary lets the team prove which payloads ever
   leave the bank's perimeter.

The next document (`objectives.md`) lists the concrete deliverables and
non-goals.
