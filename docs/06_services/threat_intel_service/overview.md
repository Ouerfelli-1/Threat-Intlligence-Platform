# threat-intel — Overview

## Purpose

Ingests supply-chain advisories and public disclosures (RSS), performs
HIBP domain-breach lookups, and generates the platform's richest AI
insight: a hunting hypothesis + Wazuh rule + extracted IOCs + ATT&CK
attack flow per threat. It also auto-promotes extracted IOCs into the
central IOC library.

| Property | Value |
|---|---|
| Port | 8003 |
| Schema | `threat` |
| Source | `services/threat-intel/` |
| Scheduler trigger | `POST /ingest/run` every 4h |
| Secrets | `HIBP_API_KEY` (optional), AI provider keys |
| Inline calls | flowviz `/flows`, ioc-collector `/indicators`, cmdb `/profile/latest` |

## Tables

| Table | Purpose |
|---|---|
| `threats` | type (supply_chain/data_breach/leak/disclosure/report), title, severity, details, analyst_status |
| `hibp_breaches` | HIBP breach records keyed by name |
| `threat_insights` | AI payload (hypothesis, wazuh_rule, IOCs, attack_flow), `prompt_version` |
| `threat_notes` | analyst notes |
| `source_health` | per-source circuit state |

## The multi-leg AI insight (the flagship feature)

`POST /threats/{id}/analyze` generates three artefacts. This is the most
intricate request in the platform.

```mermaid
sequenceDiagram
    autonumber
    participant U as Amira
    participant TI as threat-intel
    participant PG as threat_insights
    participant L as LiteLLM
    participant FV as flowviz
    participant IOC as ioc-collector
    U->>TI: POST /threats/{id}/analyze {force?}
    TI->>PG: cache-first check (prompt_version, has content)
    alt cached and not force
        PG-->>TI: existing insight
        TI-->>U: 200 (no AI)
    else generate (legs serialised — concurrency cap)
        TI->>L: leg 1 IOC extraction
        TI->>L: leg 2 hunting hypothesis (+ wazuh rule + TTPs)
        TI->>FV: leg 3 attack flow
        FV->>L: ATT&CK graph
        TI->>IOC: auto-promote extracted IOCs (tagged from-threat-insight)
        TI->>PG: upsert (lossless merge if a leg failed)
        TI-->>U: 200 full insight
    end
```

### Why serialised, not parallel (EC11)
GitHub Models caps concurrent requests per key (1 for gpt-5-chat, 2 for
gpt-4o). Running the legs in parallel tripped `Rate limit of N per 0s for
UserConcurrentRequests`. Serial legs never trip it regardless of the
smart-picked model.

### Cache-first + lossless merge
- Cache-first: a saved insight at the current `prompt_version` is returned
  without an AI call unless `force=true`.
- Lossless merge: if a fresh run's leg fails (quota) but the previous row
  had content, the old content is carried over (marked
  `*_carried_over`), so a partial failure never destroys good data.

### Smart model picker
`_SMART_MODEL_DEFAULTS = [github/gpt-4.1, github/gpt-5-chat, github/gpt-4o,
anthropic/claude-3-5-sonnet]` — prefers the largest-quota model first
(commit `61ba20a`).

## Architecture

```mermaid
graph TD
    subgraph ti["threat-intel :8003"]
        RSS["sources/rss.py"]
        HIBP["HIBP lookup"]
        ANALYZE["routes/threats.py /analyze"]
        PROMPTS["prompts.py (v3, internet-aware)"]
        MODELS["models"]
    end
    CMDB["cmdb /profile/latest"]
    FV["flowviz"]
    IOC["ioc-collector"]
    L["litellm"]
    ORCH["orchestrator /internal/notify"]
    PG[("Postgres threat schema")]

    RSS --> EXT["supply-chain RSS"]
    HIBP --> CMDB
    HIBP --> HIBPAPI["HIBP API"]
    ANALYZE --> L
    ANALYZE --> FV
    ANALYZE --> IOC
    RSS -->|new supply_chain| ORCH
    ANALYZE --> PROMPTS
    ANALYZE --> MODELS --> PG
```

## HIBP integration

At each cycle, reads company `public_domains` from cmdb `/profile/latest`,
then queries HIBP per domain. Skipped gracefully when no `HIBP_API_KEY`.

## Supply-chain notification

When ingest adds a new `supply_chain` threat, it emits
`threat.supply_chain` to the orchestrator's `/internal/notify`, feeding the
notification subsystem.

## Prompt evolution

`prompts.py` `PROMPT_VERSION` is at `v3`: long-form, internet-aware
("don't say 'no info' — use public reporting"), Splunk SPL output dropped
(Wazuh-only deploy), 5–8 sentences with named campaigns + Sysmon/MITRE
specifics. Bumping the version invalidates cached insights platform-wide.
