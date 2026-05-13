# TIP Platform — Planning & Implementation Prompt

## Your Task

You are planning and implementing a modular, AI-driven Threat Intelligence Platform (TIP).
For each service described below, you will design the full architecture, define the data
models and API contract, write the implementation, and produce the Dockerfile.
Services are built one at a time. The orchestrator is built last.

Do not ask for clarification — make the best technical decision for each open question
and document your reasoning inline. Prefer explicit, production-grade code over stubs.

**Stack:** Python, FastAPI, Docker, Redis (caching), PostgreSQL (persistence)

**Folder convention:**
- New services go in `services/<name>/`
- Pre-existing services to refactor are in `AvailableServices/` — read them before touching anything
- Shared library code goes in `packages/`

**Ignore everything else at the workspace root.** Other folders you may see (e.g., `Auth/`,
`Security_Watch/`, `Backbone/`, `tests/`) are legacy, abandoned, or unrelated code.
Do not read them, do not reference them, do not reuse them. They do not represent
the target architecture. Start fresh from this prompt.

**After completing the planning phase** (before writing any code), generate a `CLAUDE.md`
file at the project root. It must give any future developer instant context:
what each service does, its port number, its PostgreSQL tables, its required env vars,
and the commands to build and run it locally. Update it after each service is complete.

---

## What You Are Building — Context & Users

This platform is built for a **Security Operations team** at a mid-sized enterprise
(finance sector, North Africa, ~500–1000 employees). The team has one dedicated
threat intelligence analyst and two to three SOC analysts who handle daily operations.

**The problem they have today:**
The security team is drowning in disconnected data. They subscribe to a dozen threat
feeds, monitor CVE advisories, watch RSS blogs from security vendors, and manually
check ransomware victim lists. Everything lives in separate tabs, separate tools,
separate spreadsheets. When an alert fires in their SIEM (Wazuh), they spend 40 minutes
per alert manually cross-referencing IOCs against VirusTotal, checking if the CVE
affects their stack, and hunting for threat actor attribution — only to conclude that
half the alerts are not relevant to their industry or region.

They have no single answer to "who is most likely to attack us right now?" and no
quick way to investigate whether a suspicious IP seen in a log is known infrastructure
for a tracked adversary.

**The three people who use this platform every day:**

*Yassine — SOC Analyst (primary user)*
Yassine handles first-line alert triage. He needs to look up an IOC in under 10 seconds,
see immediately whether it's known-malicious and what campaign it belongs to, then decide
whether to escalate or close. He is not a threat intelligence expert — he needs the
platform to surface relevant context without him having to search for it. He also uses
the indicator investigation feature to check suspicious IPs from logs before escalating
to the TI team.

*Amira — Threat Intelligence Analyst (power user)*
Amira owns the intelligence library. She tracks specific threat actor groups that target
North African financial institutions, writes weekly threat briefings, and maintains the
watchlists of CVEs relevant to the bank's software stack. She uses the platform to:
browse actor profiles and victim lists, read AI-generated intelligence briefs, pivot
from a CVE to which actors exploit it, and draft reports with pre-populated intelligence
cards. She expects full detail — not summaries — with sources and confidence scores.

*Karim — Security Manager (decision-maker)*
Karim reads one briefing per day. He wants to see: three things the team should care
about this week, whether any new ransomware group has targeted a company like theirs
in the last 7 days, and whether any CVE in their software stack is actively exploited.
He does not investigate — he makes go/no-go decisions based on what the platform
surfaces to him. The platform's executive intelligence output (orchestrator) is built
primarily for Karim.

**The outcome the team expects:**
Open the platform in the morning and immediately know: what changed overnight, what
threats are relevant to us, and what we should act on today — without having to search
across 10 tools to reconstruct that picture manually.

---

## Cross-Cutting: Fault Tolerance & Source Resilience

Many data sources the platform ingests from are external and unreliable — they can be
down, slow, returning garbage, or rate-limiting at any time. **The platform must never
corrupt its state, stall, or crash because a source is unavailable.** This rule applies
to every service that calls an external API, feed, or third-party endpoint.

**Design rules you must enforce in every ingestion service:**

- **Source isolation** — each source (feed, API, provider) is wrapped in its own
  independent fetch function. A failure in one source must not affect the others running
  in the same ingestion cycle. Use `asyncio.gather(..., return_exceptions=True)` or
  equivalent — never `asyncio.gather` without exception handling.

- **Timeout on every outbound call** — every HTTP request to an external source must
  have an explicit timeout (connect + read). Default: 10s connect, 30s read. No call
  should ever block indefinitely.

- **Retry with exponential backoff** — transient failures (5xx, connection reset,
  timeout) are retried up to 3 times with exponential backoff and jitter before the
  source is marked as failed for that cycle. Do not retry 4xx responses.

- **Circuit breaker per source** — if a source fails 5 consecutive cycles, mark it
  as `degraded` and skip it in subsequent cycles until it recovers. Log the degradation.
  Do not let repeated failures pile up retry load.

- **Partial success is success** — if 3 out of 5 sources return data and 2 are down,
  the ingestion cycle is still considered successful. The service stores what it got
  and logs which sources failed. The scheduler sees the job as completed, not failed.

- **Stale data over blocking** — if a source is down, the platform continues serving
  whatever data it has from the previous successful fetch. Never block a read API
  waiting for fresh data from an unavailable source.

- **Per-source health tracking** — each service maintains a `source_health` table
  (source name, last success, last failure, consecutive failures, status). This is
  exposed via a `/health/sources` endpoint so the operator can see which feeds are
  currently degraded.

- **Failure logging** — every source failure is logged with: source name, timestamp,
  error type, HTTP status (if applicable), and which cycle it occurred in. Failures
  are not silently swallowed.

- **No cascading failures** — a failure in an ingestion service must not cause
  the scheduler, the orchestrator, or any other service to fail. Services are
  independently deployable and independently failable.

---

## Cross-Cutting: Confidence Scoring

Every piece of intelligence produced by the platform carries a confidence score (0.0–1.0).
Scores are computed from:
- **Source reliability** — known feed quality, historical accuracy
- **Corroboration** — how many independent sources report the same thing
- **Freshness** — recency of the data
- **Extraction quality** — structured feed vs. text extraction vs. AI inference

Confidence scores apply to: IOCs, CVE relevance assessments, threat actor attributions,
TTP mappings, and orchestrator-generated intelligence reports. They are stored alongside
the data and always returned in API responses.

---

## Cross-Cutting: AI Threat Insight (per threat/article/CVE)

When an analyst opens any threat, article, CVE, or intelligence item, the platform can
produce an **AI Insight** on demand. This insight is generated by the orchestrator's AI
and covers:

- **TTPs** — MITRE ATT&CK techniques identified, with confidence score per TTP
- **IOCs** — indicators extracted or associated, with type, value, and confidence
- **Possible threat actor** — best match from the threat-actors DB, clearly marked as
  confirmed or inferred, with confidence score and supporting evidence
- **Relevance to us** — why this matters to the company based on the profile
- **Recommended actions** — patch, block, monitor, escalate

The AI performs this by:
1. Using the item's own content as primary input
2. Searching across locally stored intelligence (IOCs, articles, CVEs, actor profiles)
3. Using web search (via a search-enabled model or tool call) to cross-reference
   against current public knowledge and corroborate or contradict the finding

The insight is cached per item. Re-running regenerates it fresh.

---

## Cross-Cutting: Platform Intelligence Output (what the platform produces)

The orchestrator continuously maintains and updates the following intelligence products,
which feed the frontend and the API:

- **Threat actors most likely to target us** — ranked list with TTPs, recency, targeting
  evidence, and confidence score. Updated each analysis cycle.
- **New threats relevant to us** — filtered and ranked threat reports from `threat-intel`
  and `news-collector`, scored for relevance against the company profile.
- **New CVEs relevant to us** — filtered from `vuln-intel` by matching against company
  software/devices. Includes EPSS, KEV status, and AI-generated exploitation context.
- **Geopolitical predictions** — AI-generated assessment of what threats are likely to
  emerge based on the current geopolitical situation and the company's country exposure.
  Updated daily.
- **Intelligence library** — browsable, searchable collection of:
  - Threat actor profiles (name, aliases, TTPs, tools, targets, ransomware status)
  - IOC list (type, value, source, confidence, first/last seen)
  - TTP catalog (MITRE technique, which actors use it, recent activity)
  - Tool profiles (malware/tooling used by tracked actors)

---

## Services to Build (in order)

### 1. `news-collector` — News Ingestion
Pulls articles and security news from multiple RSS feeds, blogs, and OSINT sources.
Normalizes articles into a common schema (title, source, date, url, summary, tags).
Deduplicates by URL hash. Stores in DB. Exposes REST API to query collected articles.

**Default RSS/feed sources (seeded at startup — operator can add more via API):**
- The Hacker News — `https://feeds.feedburner.com/TheHackersNews`
- Malwarebytes Labs — `https://www.malwarebytes.com/blog/feed`
- Tenable Blog — `https://www.tenable.com/blog/feed`
- Recorded Future Blog — `https://www.recordedfuture.com/feed`
- StepSecurity Blog — `https://www.stepsecurity.io/blog/rss.xml`
- CISA Cybersecurity Advisories — `https://www.cisa.gov/cybersecurity-advisories/feed`
- CISA ICS Advisories — `https://www.cisa.gov/ics-advisories/feed`

The feed list is stored in the DB and editable at runtime via the API. The service
pulls from all configured feeds each cycle; adding a new feed takes effect immediately
on the next scheduled run.

### 2. `vuln-intel` — Vulnerability Intelligence
Pulls new CVEs, EPSS scores, and CISA KEV (Known Exploited Vulnerabilities) data.
Also queries Taranis AI for vulnerability-related articles and enriches CVE records.
Exposes endpoints: latest CVEs, KEV feed, CVE detail, CVEs by severity/product.

**NVD API key:** Optional but strongly recommended. Without a key the NVD public API
allows 5 requests per 30-second rolling window. With a key the limit is 50 requests
per 30 seconds. If `NVD_API_KEY` is not present in the `secrets` service, the service
paces requests automatically to stay within the unauthenticated limit — no failure,
just slower full-dataset syncs.

### 3. `threat-intel` — Threats, Supply Chain, Data Leaks
Pulls supply chain threat data, data leak disclosures, and general threat reports.
Sources: RSS feeds, leak monitoring APIs, public disclosure trackers.
Normalizes to a common threat record schema. Exposes REST query API.

**Have I Been Pwned (HIBP) — domain breach monitoring:**
If `HIBP_API_KEY` is configured in the `secrets` service, this service queries the
HIBP domain search API at each ingestion cycle to check whether any of the
organization's public domains (from the company profile) appear in known data breaches
or paste dumps. Results are stored as threat records with `type: data_breach` and
surfaced in the threat feed with breach name, date, and affected data classes.
If no key is configured this source is skipped gracefully.

### 4. `ioc-collector` — Indicator of Compromise Ingestion
Pulls IOCs (IPs, domains, hashes, URLs) from threat feeds (ThreatFox, MalBazaar, OTX, etc.).
Deduplicates by indicator value + type. Each IOC carries a confidence score computed from
source reliability, corroboration count, and freshness.
Exposes: search by value, bulk lookup, feed by type, confidence-filtered queries.

**abuse.ch unified API key:** ThreatFox and MalBazaar are both operated by abuse.ch.
A single API key covers both — stored in `secrets` as `ABUSECH_API_KEY`. Both sources
use this same key; do not create two separate secret entries.

### 5. `threat-actors` — Threat Actor, Ransomware & Tool Intelligence

This service is the full intelligence library for tracked adversaries, ransomware
groups, malware families, and their tools. It is pre-seeded on first launch and
continuously refreshed from multiple sources.

**Data seeded and refreshed from:**
- **MITRE ATT&CK** — actor profiles, TTP mappings, software/tool catalog (authoritative)
- **ransomware.live** — active ransomware groups, recent victims, target sectors/countries
- **MITRE D3FEND / CAPEC** — attack pattern enrichment
- **Malpedia** — malware family profiles, actor-to-malware mappings
- **vx-underground** — malware sample metadata and group attribution
- **ThreatFox** (abuse.ch) — active malware C2 infrastructure linked to groups
- **Ransomware.live API** — victim list, group activity timeline, negotiation leaks
- **GitHub: awesome-threat-intelligence** — curated group profiles (periodic sync)
- *(user-defined additional sources can be plugged in)*

**What is stored and exposed:**

*Threat Actor Profiles:*
- Name, aliases, suspected origin country, motivation (financial, espionage, hacktivist)
- Active since / last seen dates
- Target sectors (e.g., finance, healthcare, government, energy)
- Target countries
- TTPs mapped to MITRE ATT&CK techniques with confidence scores
- Associated tools, malware families, and ransomware variants
- Notable campaigns and victims
- Ransomware group status (active / inactive / rebranded)

*Ransomware Group Profiles:*
- Group name, aliases, status, first/last seen
- Ransomware variant(s) used
- Victim list from ransomware.live (sector, country, date, company name if public)
- Ransom demand ranges (where available)
- Leak site URL
- TTP chain (how they operate: initial access → persistence → exfiltration → encryption)

*Tool & Malware Catalog:*
- Tool/malware name, type (RAT, loader, ransomware, stealer, C2 framework, exploit kit)
- Actors/groups known to use it
- MITRE techniques it implements
- Known IOCs associated with it (C2s, hashes)
- Detection references (Sigma rules links, YARA references)

Exposes a REST API for querying actors, ransomware groups, tools, and TTPs — with filtering by sector, country, and motivation. Seed runs once at startup if DB is empty. Refresh runs on the scheduler.

### 6. `integrations` — External Platform Integration

Connects to two external platforms: **Wazuh** (SIEM) and **MISP** (threat intelligence sharing).
Exposes a unified REST API used by the orchestrator for correlation against the internal
environment. Credentials for both are fetched from the `secrets` service at startup.

**Wazuh integration:**
- Wazuh exposes a REST API on port 55000 (HTTPS)
- Authentication: POST to `/security/user/authenticate` with Basic auth (username + password)
  returns a JWT token; use that Bearer token for all subsequent calls
- Pull recent security alerts: `GET /alerts` with time-range filters
- Pull agent inventory: `GET /agents` — returns hostname, IP, OS, agent version, last seen
- Store alerts in a local `wazuh_alerts` table (alert ID, agent ID, rule ID, description,
  severity, timestamp); upsert on alert ID to stay idempotent
- Sync runs on the scheduler (`wazuh_sync` job, every 30 minutes)

**MISP integration (bidirectional IOC sync):**
- MISP exposes a REST API; auth via `Authorization: {MISP_API_KEY}` header
- **Pull from MISP:** fetch recent events (`GET /events/index`) and their attributes;
  normalize IOCs into the same schema as `ioc-collector` and upsert into a local
  `misp_iocs` table
- **Push to MISP:** when new high-confidence IOCs are collected by `ioc-collector`,
  push them to MISP as new event attributes (`POST /attributes/add/{event_id}`)
- Sync runs on the scheduler alongside the wazuh sync

Exposes a REST API for: recent Wazuh alerts (filterable by severity, agent, time range),
agent inventory, MISP events and attributes, and manual sync triggers.

### 6b. `cmdb` — Asset Inventory
Internal database for organizational assets. Not an external integration — owned by the platform.
Assets: hostname, IP, OS, software installed, device type, criticality, owner, location.
Full CRUD: add assets, update them, delete them. Bulk import via CSV or JSON.
The orchestrator reads this to match CVEs and threats against what the org actually runs.

Exposes a REST API for full CRUD on assets, bulk import, and search by hostname, IP, or software name.

### 7. `flowviz` — Attack Flow Visualization *(refactor needed)*
Receives a threat description and returns a structured attack flow (MITRE ATT&CK chain).
The existing codebase is in `AvailableServices/flowviz/` — read it fully before making
any changes. It currently has an embedded frontend and no REST API.
**Your job:** strip the frontend entirely, keep the core attack-flow generation logic,
and wrap it with a clean FastAPI REST API. Input is a threat description; output is a
structured attack flow JSON. Do not touch the internal tool logic — only add the API layer
and remove the UI.

### 8. `asm` — Attack Surface Management *(refactor needed)*
The existing codebase is in `AvailableServices/asm/` — read it fully before making any
changes. It currently has an embedded frontend and no REST API, and it runs active
network scans.
**Your job:** strip the frontend entirely, remove all active scanning code, keep only
the passive discovery logic (certificate transparency via crt.sh, passive DNS, Shodan
InternetDB), and expose everything through a new FastAPI REST API.
Exposes: discovered subdomains, exposed services, certificate data.

### 9. `domainwatch` — Domain Monitoring *(needs API)*
The existing codebase is in `AvailableServices/domainwatch/` — read it fully before
making any changes. It currently has an embedded frontend and no REST API. The core
logic periodically checks a domain for changes and takes screenshots.
**Your job:** strip the frontend entirely and add a FastAPI REST API layer on top of
the existing monitoring logic. The API must support registering domains to watch,
retrieving change history with screenshots, and fetching the latest snapshot.
Do not rewrite the monitoring logic — only add the API and remove the UI.

### 10. `scheduler` — Unified Schedule Control

A single service that owns all recurring jobs across the platform. Every automated
activity is configured here — nothing runs on a hardcoded timer buried inside another
service.

**APScheduler setup:**
- Scheduler class: `AsyncIOScheduler` (runs inside the FastAPI event loop)
- Job store: `SQLAlchemyJobStore` backed by PostgreSQL — jobs survive restarts
- Executor: `AsyncIOExecutor` — all job functions are `async def`
- Job defaults: `coalesce=True` (missed runs collapse to one), `max_instances=1`
  (no overlapping runs of the same job), `misfire_grace_time=300` (5-minute window)
- Scheduler starts in the FastAPI `lifespan` context manager (`startup` / `shutdown`)
- All built-in jobs are registered at startup with `replace_existing=True` so
  redeploying the service does not create duplicate entries in the job store

**Job registration pattern:**
Each job is registered with:
- `id` — stable string key (e.g., `"news_collector_pull"`)
- `name` — human-readable label
- `trigger` — `CronTrigger` (configurable fields: `hour`, `minute`, `day_of_week`, etc.)
- `func` — an `async def` that makes an authenticated HTTP call to the target service
- `kwargs` — any static parameters (e.g., target service URL, auth token)

Jobs do **not** contain business logic — they are thin callers that POST/GET to the
relevant service endpoint. The actual work happens inside the target service.

**Job execution model:**
When a job fires, it calls the target service's trigger endpoint (e.g.,
`POST http://news-collector/ingest/run`). The scheduler records the result (success/fail,
duration, HTTP status) in a `job_run_history` PostgreSQL table. Jobs are independent —
one failure does not block others.

**Built-in jobs (registered at startup):**

| Job ID | Target service | Default schedule |
|--------|---------------|-----------------|
| `news_pull` | `news-collector` `POST /ingest/run` | Every 2 hours |
| `threat_intel_pull` | `threat-intel` `POST /ingest/run` | Every 4 hours |
| `vuln_cve_refresh` | `vuln-intel` `POST /refresh/nvd` | Every 6 hours |
| `vuln_kev_refresh` | `vuln-intel` `POST /refresh/kev` | Daily at 06:00 |
| `vuln_epss_refresh` | `vuln-intel` `POST /refresh/epss` | Daily at 06:30 |
| `ioc_pull` | `ioc-collector` `POST /ingest/run` | Every 3 hours |
| `actors_refresh` | `threat-actors` `POST /refresh` | Daily at 03:00 |
| `asm_discovery` | `asm` `POST /scan/run` | Daily at 02:00 |
| `domainwatch_check` | `domainwatch` `POST /check/run` | Every 12 hours |
| `wazuh_sync` | `integrations` `POST /wazuh/sync` | Every 30 minutes |
| `orchestrator_analysis` | `orchestrator` `POST /analyze` | Every 6 hours |
| `geo_prediction` | `orchestrator` `POST /analyze/geo` | Daily at 05:00 |

Exposes a REST API for listing jobs and their status, triggering jobs on demand, updating schedules at runtime, viewing run history, and managing ad-hoc jobs. Write operations require `scheduling:write`; reads require `scheduling:read`.

**Job history schema (stored in `job_run_history` table):**
```
run_id        UUID primary key
job_id        text references the APScheduler job id
triggered_at  timestamp
completed_at  timestamp (null if still running)
duration_ms   integer
status        text — "success" | "failed" | "timeout"
http_status   integer — response from target service
error_detail  text (null on success)
```

### 11. `auth` — Authentication & Granular RBAC

Handles all authentication and access control for the platform.
Every API request across all services is validated through this service.

**Authentication:**
- JWT-based (RS256). Login returns access token + refresh token.
- Session management: list active sessions, revoke a session.

**RBAC model — additive privileges:**
- A **Role** is a named collection of permissions (e.g., `analyst`, `admin`, `viewer`)
- A **User** is assigned one role and optionally a set of supplementary permissions
- Effective permissions = role permissions UNION supplementary user permissions
- No permission subtraction — the model is purely additive
- Admins can create/edit/delete roles and define which permissions they include

**Permission granularity examples:**
`intelligence:read`, `intelligence:ask`, `actors:read`, `iocs:read`,
`assets:write`, `assets:delete`, `scheduling:write`, `users:manage`,
`secrets:read`, `secrets:write`, `reports:read`, `asm:read`, `domainwatch:write`

**Admin-only capabilities:**
- Create, edit, delete users
- Create, edit, delete roles
- Assign roles to users
- Grant/revoke supplementary permissions per user
- View all active sessions and force-revoke any session
- Access secrets management

Exposes a REST API for login, token refresh, current user profile, user and role management (admin only), supplementary permission assignment, and session listing and revocation.

### 12. `secrets` — Centralized Secrets & API Key Management

One place to store and manage every credential the platform uses:
OpenRouter API key, Wazuh credentials, MISP API key, OTX API key, ThreatFox key,
any feed API key, SMTP credentials, webhook secrets, etc.

Secrets are stored encrypted at rest (Fernet symmetric encryption, key from env).
Services fetch their secrets from this service at startup via authenticated internal API.
No secret is hardcoded in any service or `.env` file at runtime — all go through here.

Exposes a REST API (admin only, `secrets:read` / `secrets:write`) for listing secret names and metadata, creating, updating, and deleting secrets, retrieving values with access logging, and triggering rotation. Surfaced in the UI as a credential vault panel visible only to admins.

### 13. `indicator-intel` — AI-Driven IP & Domain Investigation

On-demand deep investigation of a single IP address or domain name. The analyst submits
an indicator; the service queries every available source in parallel, aggregates the raw
findings, cross-references against the platform's local intelligence, and feeds everything
to the AI, which produces a structured verdict. Results are stored and retrievable by
indicator value.

**This service is passive only** — it queries APIs and databases; it never connects
directly to the target IP or domain.

**What is investigated:**

*Network & ASN intelligence:*
- Geolocation (country, city, coordinates) and ASN data via **ip-api.com**
  (free tier, no API key required, 45 requests/minute; live API call per indicator;
  fields: country, regionName, city, lat, lon, isp, org, as, query)
- ASN number, ASN name, owning organization, network range
- ASN reputation: is this ASN known to host malicious infrastructure? Is it attributed
  to a threat actor (e.g., bulletproof hosting, state-sponsored infrastructure)?
  Checked against curated ASN blocklists from the
  [awesome-threat-intelligence](https://github.com/hslatman/awesome-threat-intelligence)
  collection and cross-referenced with the local `threat-actors` service

*Shodan enrichment (API key from `secrets` service):*
- Open ports and running services (banners, software versions)
- Known vulnerabilities associated with detected services (Shodan CVE data)
- Historical scan data — when was this IP first/last seen, what changed
- Hostnames and domains resolving to this IP
- Tags (e.g., `vpn`, `tor`, `cloud`, `honeypot`, `self-signed`)

*DNS & registration data:*
- Forward/reverse DNS (PTR records)
- WHOIS / RDAP: registrar, registration date, expiry, registrant org, name servers
- Subdomains (from certificate transparency logs via crt.sh)
- Historical passive DNS resolutions (what IPs this domain has pointed to, what domains
  have resolved to this IP)

*Threat intelligence cross-reference:*
- Check against local IOC database (`ioc-collector`) — is this indicator already known?
  If so, include source, first seen, confidence score, and malware family association
- Check against `threat-actors` service — is this IP/domain linked to a known actor's
  infrastructure, C2 servers, or campaign?
- Check against curated IP/domain/ASN reputation lists from
  [awesome-threat-intelligence](https://github.com/hslatman/awesome-threat-intelligence):
  includes Emerging Threats, Feodo Tracker, Abuse.ch, Spamhaus, Team Cymru,
  CINS Score, PhishTank, OpenPhish, and others in that collection

*Research lab mention search:*
- Searches the platform's collected articles (`news-collector`) for mentions of this
  indicator in reports published by research labs: WatchTowr, Mandiant, Google TAG,
  Unit 42, Wiz.io, Recorded Future, Sekoia, ESET, Sophos, CrowdStrike, Microsoft MSTIC
- Returns matching article titles, publication dates, and excerpts

**IntelOwl integration:**
If an IntelOwl instance is configured (API key in `secrets`), the service also submits
the indicator to IntelOwl and merges its aggregated results. IntelOwl covers dozens of
analyzers (VirusTotal, AbuseIPDB, OTX, Greynoise, MalwareBazaar, etc.) in a single call.
If IntelOwl is not configured, the service operates without it — no degradation.

**AI synthesis:**
After all sources are queried (with the fault tolerance rules from the cross-cutting
section applied — source failures are isolated), the raw findings are passed to the AI
(via OpenRouter). The AI produces a structured verdict:

```json
{
  "indicator": "185.220.101.42",
  "type": "ip",
  "verdict": "malicious",
  "confidence": 0.91,
  "summary": "This IP is a Tor exit node operated by a known bulletproof ASN (AS205100)
               previously associated with REvil infrastructure. It appears in 4 threat
               feeds and was mentioned in a Mandiant report (2024-11) as part of a
               ransomware campaign targeting financial sector organizations.",
  "risk_score": 87,
  "categories": ["tor_exit_node", "bulletproof_hosting", "ransomware_infrastructure"],
  "attributed_actors": [
    {"name": "REvil / Sodinokibi", "confidence": 0.72, "basis": "inferred"}
  ],
  "recommended_action": "block",
  "source_hits": {
    "shodan": true,
    "ip_api": true,
    "ioc_collector": true,
    "threat_actors": true,
    "intelowl": true,
    "asn_lists": true,
    "articles": 2
  },
  "investigated_at": "2026-05-12T08:00:00Z"
}
```

**Caching & history:**
Results are cached by indicator value. Re-investigation regenerates a fresh result and
stores it alongside previous investigations, so the analyst can track how an indicator's
reputation has changed over time.

Exposes a REST API for submitting investigation requests (synchronous for fast lookups,
async with polling for deep investigations), retrieving past investigation results by
indicator, and listing recently investigated indicators.

---

## Orchestrator (built last, before frontend)

### `orchestrator` — AI-Driven Intelligence Engine

The brain of the platform. Runs on a schedule and on-demand. Does not collect data
itself — it reads from all the service APIs above and reasons over them.

**Inputs:**
- Company profile: sector, countries of operation, software/hardware in use
- Latest CVEs and KEV entries (from `vuln-intel`)
- Active threat actors and their TTPs (from `threat-actors`)
- IOCs seen locally / Wazuh detections (from `integrations`)
- Current news and threat reports (from `news-collector`, `threat-intel`)
- Recent indicator investigation results (from `indicator-intel`) — used to correlate
  known-malicious infrastructure against threat actor campaigns

**What it does:**
1. Identifies CVEs and exploits that are relevant to the company profile
2. Identifies which threat actors are most likely to target the company
3. Cross-references local detections (Wazuh) with known IOCs and TTPs
4. Generates intelligence briefs: what is happening, what to expect, recommended actions
5. Calls `flowviz` to generate attack flow visualizations for top threats
6. Stores results as intelligence reports accessible via API

Exposes a REST API for triggering analysis cycles, retrieving generated reports, checking run status, and submitting ad-hoc intelligence requests.

**AI:** Uses OpenRouter (API key in env, model is configurable). The AI is the one
producing the intelligence — it receives structured context and returns structured
output. Prompts are defined per analysis step with a fixed JSON output schema.
No free-form chat interface.

**Prompt design reference:** Model the orchestrator's analysis prompts after the
patterns in the [Feedly Cyber Threat Intelligence Prompt Library](https://feedly.com/ti-essentials/posts/cyber-threat-intel-prompt-library).
Pay particular attention to: threat summarization prompts, actor attribution prompts,
relevance scoring prompts, and IOC extraction prompts — these map directly to the
orchestrator's four main analysis steps.

**Ad-hoc intelligence (`POST /ask`):**
The analyst submits any combination of:
- A raw article, report excerpt, or paste of text
- A specific question or prompt ("is this relevant to us?", "what TTPs are used here?")
- Optionally: a CVE ID, IOC, or threat actor name to focus on

The orchestrator automatically injects the company profile as context, then sends
the full payload to the LLM. The response is structured intelligence:
what the input means for the organization, relevant TTPs, recommended actions,
and whether it warrants escalation. Response is saved as an ad-hoc report.

---

## Company Profile Schema (used by orchestrator)

The company profile is the static organizational context injected into every AI analysis.
Asset inventory (specific hostnames, IPs, installed software per machine) lives in the CMDB.
This profile captures who the organization is, what it runs, where it operates, and what matters most.
It is stored in the `cmdb` service, editable via the UI, and versioned (changes are audited).

```json
{
  "identity": {
    "name": "Acme Corp",
    "sector": "finance",
    "sub_sector": "retail banking",
    "employee_count_range": "500-1000",
    "hq_country": "TN",
    "countries_of_operation": ["TN", "FR", "DE"],
    "public_domains": ["acme.com", "acme.tn", "acme.fr"],
    "language": "en"
  },

  "technology": {
    "operating_systems": ["Windows Server 2022", "Ubuntu 22.04", "RHEL 9"],
    "endpoint_os": ["Windows 11", "Windows 10"],
    "software": ["Microsoft Exchange", "SharePoint", "SAP ERP", "Oracle DB"],
    "network_devices": ["Fortinet FortiGate", "Cisco IOS", "Palo Alto PAN-OS"],
    "cloud_providers": ["Azure", "AWS"],
    "identity_providers": ["Active Directory", "Azure AD"],
    "remote_access": ["Citrix", "GlobalProtect VPN"],
    "security_tools": ["Microsoft Defender", "Wazuh", "Tenable.io"],
    "industrial_ot": false
  },

  "exposure": {
    "internet_facing_services": ["Web portal", "Email gateway", "VPN", "API"],
    "mobile_workforce": true,
    "third_party_access": true,
    "supply_chain_vendors": ["Microsoft", "Fortinet", "SAP", "Cisco"],
    "critical_data_types": ["customer PII", "financial records", "payment card data"]
  },

  "compliance": {
    "regulatory_frameworks": ["PCI-DSS", "GDPR", "Central Bank of Tunisia regulations"],
    "certifications": ["ISO 27001"],
    "data_residency_requirements": ["TN", "EU"]
  },

  "geopolitical": {
    "geopolitical_regions": ["North Africa", "Western Europe"],
    "conflict_adjacent": false,
    "notable_partnerships": ["EU financial institutions", "African Development Bank"],
    "sanctions_exposure": false
  },

  "risk": {
    "risk_appetite": "low",
    "crown_jewels": ["core banking system", "customer database", "payment processing"],
    "previous_incidents": ["phishing campaign 2024", "credential stuffing 2023"],
    "threat_concerns": ["ransomware", "insider threat", "supply chain attack", "fraud"]
  }
}
```

The orchestrator uses every field. `technology` drives CVE and TTP relevance matching.
`exposure` and `supply_chain_vendors` drive supply chain threat scoring.
`geopolitical` feeds the geopolitical prediction engine.
`risk.crown_jewels` and `risk.threat_concerns` weight the AI's prioritization output.

---

## Key Rules

- Every service has its own `Dockerfile` and exposes a FastAPI REST API
- No service talks directly to another service's database — only via API
- Redis is used for caching hot data (IOC lookups, CVE summaries)
- All data is stored in PostgreSQL — one shared DB, separate tables per service
- The orchestrator is the only service that calls other services directly
- ASM and DomainWatch do not perform active network probing
- FlowViz input/output is always JSON over HTTP

**Port assignments (fixed — do not deviate):**

| Service | Port |
|---------|------|
| `auth` | 8000 |
| `news-collector` | 8001 |
| `vuln-intel` | 8002 |
| `threat-intel` | 8003 |
| `ioc-collector` | 8004 |
| `threat-actors` | 8005 |
| `integrations` | 8006 |
| `cmdb` | 8007 |
| `flowviz` | 8008 |
| `asm` | 8009 |
| `domainwatch` | 8010 |
| `scheduler` | 8011 |
| `secrets` | 8012 |
| `indicator-intel` | 8013 |
| `orchestrator` | 8014 |

**Service-to-service URL convention:**
Every service that calls another service reads the target URL from an environment variable
named `{SERVICE_NAME_UPPER}_URL` (e.g., `NEWS_COLLECTOR_URL=http://news-collector:8001`,
`ORCHESTRATOR_URL=http://orchestrator:8014`). No service URL is hardcoded. The scheduler
uses these env vars when making HTTP calls to trigger jobs. Docker Compose sets these
vars using the service name as the hostname.

**JWT validation across services:**
The `auth` service issues RS256 JWTs. Every other service validates incoming tokens
locally using the **public key only** (injected via environment variable at startup).
No service calls the auth service on the hot path. Token validation is a local
cryptographic check — fast, no network dependency. The auth service is only called
for login, refresh, session management, and user/role admin operations.

**AI usage principle — AI reads processed data, never raw feeds:**
The platform follows a strict separation: automated jobs pull, normalize, deduplicate,
and store data without any AI involvement. The AI is only invoked after data is already
clean and structured in the database. The orchestrator reads from service APIs (not raw
feeds) and passes a curated context bundle to the LLM. This means the platform continues
to function fully — ingesting, matching, alerting — even if the LLM provider is down.

**Build order note — auth and secrets:**
Services 1–9 are built first. During development, JWT validation middleware is included
from the start but can be toggled off via a `DISABLE_AUTH=true` env flag for local
testing. When `auth` (service 11) is built, the flag is removed and all services
validate tokens against the real public key. The `secrets` service (12) similarly
uses a `FERNET_KEY` env variable from day one — no service should ever hardcode a
credential even during development.

**CLAUDE.md — required output after planning:**
After the planning phase and again after each service is completed, update `CLAUDE.md`
at the project root. Minimum required content per service:
- One-line description of what the service does
- Port number
- PostgreSQL tables it owns
- Required environment variables
- `docker build` and `uvicorn` run commands
- Any non-obvious design decisions made during implementation

The final `CLAUDE.md` must be complete enough that a new developer can understand the
entire platform, run any service locally, and know where to look to change any behavior—
without reading source code.
