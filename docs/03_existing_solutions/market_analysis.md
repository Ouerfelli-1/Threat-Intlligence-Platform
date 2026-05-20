# Market Analysis

## The CTI tooling landscape

Cyber-threat-intelligence tooling falls into four broad categories. The
platform's design borrows ideas from each while declining to adopt any
wholesale.

### 1. Commercial Threat Intelligence Platforms (TIPs)

Examples: Recorded Future, Anomali ThreatStream, ThreatConnect, Mandiant
Advantage.

- **Strengths:** vast curated feeds, mature UIs, global APT coverage,
  enterprise integrations.
- **Weaknesses for this customer:** per-seat / per-query licensing that
  does not fit a three-user SOC; off-premises data handling that
  conflicts with regional financial regulation; limited tunability of the
  relevance model toward MENA finance-sector targeting.

### 2. Open-source TIPs

Examples: MISP, OpenCTI, Yeti.

- **Strengths:** self-hosted, free, strong sharing (MISP) and a rich
  data model (OpenCTI).
- **Weaknesses for this customer:** they are *aggregation and storage*
  platforms, not *AI-synthesis-and-ranking* platforms. They answer "what
  do we know about X?" well but not "who is most likely to attack *us*
  right now, and what should the manager do today?". They also require
  significant operational expertise to run well.

The platform **integrates with** MISP (the `integrations` service
pushes/pulls) rather than replacing it — MISP remains the sharing
substrate; TIP is the analysis layer on top.

### 3. SIEM-native threat intel modules

Examples: Wazuh threat-intel modules, Splunk ES, Elastic Security.

- **Strengths:** co-located with the alerts; correlation is native.
- **Weaknesses for this customer:** scoped to the SIEM's data; weak at
  external-source aggregation and at producing executive-level synthesis.

The platform **integrates with** Wazuh (the `integrations` service pulls
alerts) and adds the cross-source correlation the SIEM lacks.

### 4. Point tools and manual workflow

Examples: VirusTotal, abuse.ch lookups, CVE databases, spreadsheets.

- **Strengths:** free, authoritative for their narrow slice.
- **Weaknesses for this customer:** this *is* the status quo the platform
  replaces — ten tools, ~40 minutes per alert, no synthesis.

The platform **consumes** these sources (abuse.ch ThreatFox/MalBazaar,
NVD, CISA KEV, EPSS, OTX, ransomware.live, HIBP) directly through its
ingester services, eliminating the manual cross-referencing.

## Positioning

The platform occupies a deliberate niche:

> A **self-hosted, single-organisation, AI-synthesis layer** that sits on
> top of open sources and the bank's existing MISP + Wazuh, tuned to the
> bank's own technology profile and region, with a single auditable AI
> egress boundary.

It is **not** trying to out-feed Recorded Future, out-store OpenCTI, or
out-correlate Splunk. It composes their categories' best ideas
(aggregation + correlation + synthesis) into one self-hosted system the
bank fully controls.

## Why "build" beat "buy" for this customer

| Criterion | Commercial TIP | Open-source TIP | This platform |
|---|---|---|---|
| Data stays on-premises | ✗ (cloud) | ✓ | ✓ |
| Single auditable AI egress | ✗ | n/a (no AI) | ✓ (LiteLLM proxy) |
| Relevance tuned to our stack/region | limited | manual | ✓ (CMDB profile + prompts) |
| Cost for 3 users | high (licensing) | low (ops cost) | low (build + host) |
| Executive daily synthesis | ✓ | ✗ | ✓ |
| Sub-10s IOC triage | ✓ | partial | ✓ (Redis hot path) |
| Custom hunting hypotheses (Wazuh rules) | partial | ✗ | ✓ |
| Operational complexity | low (SaaS) | high | medium (single-host compose) |

The decisive factors were **data sovereignty** and **relevance
tunability** — both of which a self-hosted, prompt-driven, profile-aware
platform delivers and which commercial SaaS could not within the bank's
constraints.
