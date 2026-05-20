# Domain Overview

This document establishes the cyber-threat-intelligence (CTI) domain
vocabulary used throughout the documentation, so a reader without a
security background can follow the architecture chapters.

## What "threat intelligence" means here

Threat intelligence is evidence-based knowledge about existing or emerging
threats that supports defensive decisions. In this platform it is broken
into the data types the code actually models:

| Domain concept | Where it lives | Canonical key |
|---|---|---|
| **Indicator of Compromise (IOC)** | `ioc` schema | `(type, normalized_value)` |
| **Vulnerability (CVE)** | `vuln` schema | `cve_id` (e.g. `CVE-2024-3400`) |
| **Exploitation status (KEV)** | `vuln.kev` | `cve_id` |
| **Exploitation probability (EPSS)** | `vuln.epss` | `cve_id` |
| **Threat actor / group** | `actors` schema | `mitre_id` (e.g. `G0032`) or surrogate for manual |
| **Technique (ATT&CK TTP)** | `actors.actor_ttps` | `technique_id` (e.g. `T1059.001`) |
| **Ransomware group / victim** | `actors.ransomware_*` | group name / dedup hash |
| **Threat event** | `threat` schema | surrogate UUID + `type` |
| **Article / news item** | `news` schema | `url_hash` |
| **Attack flow** | `flowviz` schema | `sha256(input + prompt_version)` |

## Indicator normalisation — why it is foundational

A single malicious domain can appear in feeds as `Example.COM`,
`example.com.`, `example[.]com` (defanged), or punycode. Corroboration —
"three sources independently report this indicator" — is only meaningful
if all three normalise to the same string.

`packages/tip_schemas/src/tip_schemas/indicators.py` `normalize(type, raw)`
implements:

- **IP** — validated, IPv4 left as-is, IPv6 lowercased without zone id.
- **Domain** — punycode-encoded, lowercased, trailing dot stripped,
  defanged forms (`[.]`, `(.)`) restored.
- **URL** — scheme lowercased, host normalised as a domain, default ports
  stripped, fragment dropped, query preserved.
- **Hash** — lowercased hex; SHA-256 / SHA-1 / MD5 disambiguated by length.

This normalised value is the cross-service join key. The orchestrator
joins IOCs to actor infrastructure by it; `indicator-intel` keys
investigations by `(type, normalized_value)`.

## Confidence scoring — the domain's "trust" model

Not every reported indicator deserves equal weight. A structured CISA
advisory is more reliable than a scraped HTML blog. The platform encodes
this in `packages/tip_schemas/src/tip_schemas/confidence.py`.

Each data type carries a weight vector summing to 1.0:

| Data type | source_reliability | corroboration | freshness | extraction_quality |
|---|---|---|---|---|
| IOC | 0.40 | 0.30 | 0.20 | 0.10 |
| CVE relevance | 0.30 | 0.10 | 0.30 | 0.30 |
| Article | 0.50 | 0.10 | 0.30 | 0.10 |
| Actor attribution | 0.40 | 0.40 | 0.10 | 0.10 |
| TTP mapping | 0.50 | 0.20 | 0.10 | 0.20 |

The score plus the **input vector that produced it** are persisted
(`confidence_score numeric`, `confidence_inputs jsonb`) so the formula can
evolve and historical rows can be re-scored.

> Note: confidence scores are persisted but, per a later product decision,
> are **not displayed** in the UI (see commit history — "remove confidence
> metrics from everywhere"). They remain available for AI ranking and
> future re-introduction.

## The MITRE ATT&CK framework

ATT&CK is a public knowledge base of adversary tactics and techniques.
The platform consumes the STIX bundle (`threat-actors` service) to seed:

- **Tactics** — the "why" (TA0001 Initial Access, TA0011 C2, …).
- **Techniques** — the "how" (T1566 Phishing, T1059 Command Interpreter, …).
- **Groups** — named actors (G0032 Lazarus, …) with technique mappings.

ATT&CK technique IDs are the canonical cross-reference between hunting
hypotheses (threat-intel / threat-actors AI insight), attack flows
(flowviz), and actor profiles.

## Wazuh and MISP — the SIEM/sharing endpoints

- **Wazuh** is the bank's SIEM. The `integrations` service pulls alerts
  and agents from it. The platform's value-add is correlating those
  alerts against known IOCs and actor TTPs (orchestrator step 3).
- **MISP** is a threat-sharing platform. The `integrations` service can
  push high-confidence (≥ 0.85) IOCs into a configured MISP event so the
  bank contributes back to its sharing community.

## The AI synthesis layer

The platform's differentiator is an AI layer that reads **processed data
only** and produces ranked, actionable output:

- **CVE relevance** — which of the latest CVEs matter to *our* tech stack.
- **Actor likelihood** — which actors are most likely to target *us*.
- **Detection correlation** — which Wazuh alerts match known IOCs/actors.
- **Executive brief** — a headline + top-3 actions for Karim.
- **Geopolitical outlook** — a 30-day regional threat forecast.
- **Hunting hypotheses** — per-threat / per-actor Wazuh rules + ATT&CK
  attack flows.

The hard architectural rule: **AI is never on the ingest hot path.** If
the LLM provider is down, ingest continues and the platform keeps serving
stored intelligence. This is enforced structurally — ingesters in
`services/*/app/sources/` never import `tip_ai`.

## Glossary

| Term | Meaning in this codebase |
|---|---|
| BFF | Backend-for-frontend — the Next.js `/api/[...path]` proxy |
| Hot path | The latency-critical IOC lookup that must stay < 200 ms |
| Source health | Per-service circuit-breaker state for external feeds |
| Insight | A persisted AI analysis payload for one resource |
| Dork | A crafted search-engine query (`site:x ext:env`) |
| Service JWT | (Legacy) a JWT minted by auth for inter-service calls — now bypassed by `DISABLE_AUTH=true` on data services |
| Prompt version | A string stamped on every AI output so prompt changes are traceable and caches invalidate |
