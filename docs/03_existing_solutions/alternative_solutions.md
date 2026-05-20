# Alternative Solutions Considered

For each major sub-problem the platform solves, an off-the-shelf
alternative existed. This document records what was considered and why the
in-house approach was chosen. Architecture-level technology choices
(FastAPI, PgBouncer, etc.) are covered separately in
`12_technology_choices/`; this document covers *product/system-level*
alternatives.

## A1 — Aggregation: adopt OpenCTI instead of building ingesters

**Alternative:** deploy OpenCTI and write connectors.

**Why not adopted:** OpenCTI's data model and STIX-centricity impose a
heavy operational footprint (Elasticsearch, RabbitMQ, MinIO, Redis,
multiple workers) for a three-user SOC. The platform's per-service
ingesters (`news-collector`, `vuln-intel`, etc.) are lighter, own their
own narrow schema, and feed the AI layer directly. OpenCTI would have
become a second platform to operate alongside the AI layer.

## A2 — Sharing/storage: store everything in MISP

**Alternative:** use MISP as the system of record.

**Why not adopted (but partially adopted):** MISP is excellent at
sharing and at the IOC/event model, but weak at CVE/EPSS/KEV modelling,
at actor likelihood ranking, and at executive synthesis. The platform
keeps its own schemas for analysis and **integrates** with MISP for the
sharing use case (push high-confidence IOCs, pull events). MISP is a
peer, not the core.

## A3 — Correlation: do it all in the SIEM

**Alternative:** push all external intel into Wazuh and correlate there.

**Why not adopted:** Wazuh correlation is rule-based and scoped to the
SIEM's ingested data; it does not produce the cross-source, AI-ranked
synthesis (CVE relevance, actor likelihood, executive brief) that is the
platform's reason to exist. The platform **pulls** Wazuh alerts and adds
the correlation layer on top (orchestrator step 3).

## A4 — AI: call the model SDK directly from each service

**Alternative:** each AI-consuming service imports the OpenAI / Anthropic
SDK and calls the provider directly.

**Why not adopted:** that scatters provider keys into every service,
couples each service to a specific provider's SDK churn, and gives no
single egress boundary to audit. Instead the platform routes all AI
through a **LiteLLM proxy** (`infra/litellm/`). Services hold only the
proxy's master key; the proxy holds the provider keys and handles
fallback. One place to rotate keys, one place to audit egress, one place
to change providers.

## A5 — Scheduling: cron in each container

**Alternative:** a crontab or APScheduler instance inside every ingester.

**Why not adopted:** that scatters scheduling logic, makes "what runs
when?" un-answerable from one place, and complicates run history. The
platform centralises all cron in one `scheduler` service with a single
`job_run_history` table and a watchdog. One service owns "when things
happen".

## A6 — Frontend data access: direct service calls + CORS

**Alternative:** the SPA calls each of the 15 services directly, with
CORS configured per service.

**Why not adopted:** that requires CORS on 15 services, leaks the internal
topology to the browser, and complicates auth-header handling. The
platform uses a **BFF** (`frontend/src/app/api/[...path]/route.ts`) — one
origin for the browser, server-side fan-out to internal services, no CORS
anywhere.

## A7 — Migrations: a single shared migration history

**Alternative:** one Alembic history for the whole database.

**Why not adopted:** that couples all services into one migration
timeline — changing one service's schema would touch a shared history and
risk conflicts. The platform gives **each service its own Alembic
directory** and runs them all from a one-shot `alembic-init` container.
Services version their schema independently.

## A8 — Notifications: a third-party alerting SaaS

**Alternative:** PagerDuty / Opsgenie / a Slack webhook integration.

**Why not adopted for v1:** those add an external dependency and an
egress path for what is, at this stage, simple email alerting. The
platform ships an in-house SMTP notification subsystem
(`services/orchestrator/app/notify/`) with a configurable rule engine.
A generic webhook channel is scaffolded in the schema (`channel` column
accepts `webhook`) for a future Slack/Discord/PagerDuty integration
without re-architecture.

## A9 — Dorking: a commercial OSINT API

**Alternative:** SpiderFoot, Maltego, or a paid OSINT aggregator.

**Why not adopted for v1:** heavyweight for the need. The platform's
dorking sub-service (`services/indicator-intel/app/dorking/`) is a
focused catalog of dork templates run through Google CSE with a free
DuckDuckGo fallback — enough to surface exposed files / leaked
credentials / paste-site mentions during an investigation, integrated
directly into the investigate page rather than a separate tool.

## Decision principle

Across every alternative the same principle held:

> **Integrate with the bank's existing substrate (MISP, Wazuh, open
> sources); build only the synthesis layer that no existing tool
> provides; keep a single auditable boundary for anything that leaves the
> host.**
