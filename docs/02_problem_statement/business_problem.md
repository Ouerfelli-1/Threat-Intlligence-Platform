# Business Problem

## The cost of fragmented tooling

The customer SOC currently operates across ten or more disconnected
tools. The product specification (`prompt/prompt.md`) quantifies the core
pain: the team spends **roughly 40 minutes per alert** manually
cross-referencing across RSS feeds, CVE databases, ransomware victim
lists, VirusTotal, and Wazuh.

This fragmentation produces three business-level failures:

### 1. No single answer to "who is most likely to attack us right now?"

Each tool answers a slice. The CVE database knows vulnerabilities; the
actor tracker knows groups; the SIEM knows alerts. **No tool combines the
company's own technology profile with the live threat landscape to
produce a ranked answer.** A security manager cannot make a defensible
go/no-go decision from ten browser tabs.

The platform addresses this directly: the orchestrator's *actor
likelihood* step (`services/orchestrator/app/analysis.py`) takes the
company profile from `cmdb` and the actor catalogue from `threat-actors`
and produces a ranked list with rationale, surfaced on the dashboard's
"Top actors relevant to us" card.

### 2. Slow pivot from indicator to actor

When an analyst sees a suspicious IP in a Wazuh alert, answering "is this
associated with a known actor?" requires manual searching across multiple
tools. By the time the answer arrives the alert may be stale.

The platform makes this a single normalised-value join: IOCs and actor
infrastructure share the same `tip_schemas.indicators.normalize` key, and
`indicator-intel` cross-references both in one investigation.

### 3. Intelligence that does not weigh the regional context

Global commercial feeds under-weight North-African finance-sector
targeting. A generic "critical CVE" feed floods the team with noise that
is not relevant to the bank's actual stack (core banking platform, SWIFT
connectivity, regional ATM networks).

The platform's AI prompts (`services/orchestrator/app/prompts.py`,
`services/threat-intel/app/prompts.py`) explicitly instruct the model to
weigh MENA-region campaigns, finance-sector targeting, and SWIFT /
payment-system implications. CVE relevance is scored *against the
company's CMDB technology list*, not in the abstract.

## Quantified business impact (target)

| Metric | Before (status quo) | Target with TIP |
|---|---|---|
| Time to triage one alert | ~40 min | < 10 min (Yassine workflow) |
| Tools touched per triage | 10+ | 1 (TIP) |
| Time for manager's daily situational awareness | scattered, never complete | one dashboard, ~3 min |
| "Is this IOC known?" answer | minutes of manual lookup | < 200 ms (Redis hot path) |
| Coverage of regional adversaries | feed-dependent, generic | prompt-weighted toward MENA finance |

> These targets are design intent from the specification. Latency targets
> (< 200 ms IOC lookup) are architecturally enforced; time-to-triage
> reduction depends on analyst adoption and is not independently measured
> in this deliverable.

## Why this is a build-vs-buy decision in the bank's favour

The detailed comparison is in `03_existing_solutions/`. The business-level
summary:

- **Data sovereignty** — regional financial regulation restricts
  off-premises movement of customer-adjacent data. A self-hosted platform
  with a single, auditable AI egress boundary (the LiteLLM proxy) lets
  the bank prove compliance.
- **Cost structure** — commercial TIP licences scale per-seat or
  per-query. The bank's three-user SOC does not justify enterprise
  licensing; a self-hosted platform converts a recurring licence to a
  one-time build plus hosting.
- **Customisation** — the bank needs the relevance model tuned to its
  own stack and region. Commercial platforms expose limited tuning;
  this platform's relevance logic is a prompt and a CMDB profile the
  bank fully controls.

## Stakeholder value mapping

| Stakeholder | Business value delivered |
|---|---|
| SOC Analyst (Yassine) | Sub-10-second triage; one tool instead of ten |
| TI Analyst (Amira) | A curated, AI-augmented library she controls |
| Security Manager (Karim) | One defensible daily brief for go/no-go calls |
| Compliance | Full audit trail + single egress boundary |
| IT Operations | One-command bring-up + one-command diagnostics |
