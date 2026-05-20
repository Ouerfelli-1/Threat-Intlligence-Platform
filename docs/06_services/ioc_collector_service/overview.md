# ioc-collector — Overview

## Purpose

Ingests IOCs from ThreatFox, MalwareBazaar, and OTX; counts corroboration
across sources; serves the platform's latency-critical lookup hot path
through Redis; and receives auto-promoted IOCs from the threat/actor AI
insights.

| Property | Value |
|---|---|
| Port | 8004 |
| Schema | `ioc` |
| Source | `services/ioc-collector/` |
| Scheduler trigger | `POST /ingest/run` every 3h |
| Secrets | `ABUSECH_API_KEY` (ThreatFox + MalBazaar), `OTX_API_KEY` (optional) |
| Cache | Redis hot path (`ioc:<type>:<value>`, 10-min TTL) |

## Tables

| Table | Purpose |
|---|---|
| `indicators` | `type, normalized_value, raw_value, first/last_seen, tags, confidence, analyst_status`; `unique(type, normalized_value)` |
| `indicator_sources` | per-source report rows; corroboration is counted from these; `pk(indicator_id, source_name)` |
| `indicator_notes` | analyst notes |

## The hot path

```mermaid
sequenceDiagram
    autonumber
    participant Y as Yassine
    participant L as /indicators/lookup
    participant R as Redis
    participant PG as Postgres
    Y->>L: POST {indicators:[{type,value}]}
    loop each indicator
        L->>L: normalize(type, value)
        L->>R: GET ioc:type:value
        alt hit
            R-->>L: cached verdict
        else miss
            L->>PG: SELECT WHERE type, normalized_value
            L->>R: SETEX (10-min TTL)
        end
    end
    L-->>Y: verdicts (< 200ms target)
```

This is the path that backs Yassine's sub-10-second triage (G9). On a
cache hit it is single-digit milliseconds and never touches Postgres.

## Corroboration scoring

When a new source reports an existing indicator: insert an
`indicator_sources` row, recompute the confidence score (corroboration =
count of distinct `source_name` rows, capped contribution), update
`last_seen`. The `confidence.py` IOC weight vector puts 0.30 on
corroboration — three independent sources materially raises confidence.

## Manual creation + auto-promotion

- `POST /indicators` — analyst-created IOC at reliability 0.95, source
  `analyst:<subject>`, status `reviewed`. Verified working end-to-end
  (admin → BFF → backend → DB returns 201).
- **Auto-promotion target** — threat-intel and threat-actors POST
  extracted IOCs here (tagged `from-threat-insight` /
  `from-actor-insight`), deduped on `(type, normalized_value)`; an
  existing indicator just gains a new source row.

## Architecture

```mermaid
graph TD
    subgraph ioc["ioc-collector :8004"]
        SRC["sources: threatfox, malbazaar, otx"]
        LOOKUP["routes/indicators.py lookup (Redis-first)"]
        CRUD["manual create + list"]
        MODELS["models: Indicator, IndicatorSource, IndicatorNote"]
    end
    ABUSE["abuse.ch"]
    OTX["AlienVault OTX"]
    R[("Redis")]
    PG[("Postgres ioc schema")]
    PROMOTERS["threat-intel / threat-actors"]

    SRC --> ABUSE
    SRC --> OTX
    LOOKUP --> R
    LOOKUP --> PG
    CRUD --> MODELS --> PG
    PROMOTERS -->|POST /indicators| CRUD
```

## Why Redis only for the hot path

Every other read in the platform goes straight to Postgres. The IOC
lookup is the single endpoint with a hard latency budget, so it is the
single endpoint with a cache. The cache is loss-tolerant (10-min TTL,
reconstructed from Postgres on miss) — wiping Redis costs a cold-cache
penalty, not data.
