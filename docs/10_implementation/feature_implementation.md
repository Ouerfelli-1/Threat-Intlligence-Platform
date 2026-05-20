# Feature Implementation (end-to-end)

This document walks five real features from request to storage, naming the
actual modules. It is the "how it all fits" complement to the
component-level documents.

## 1. IOC lookup (the hot path)

The latency-critical feature — Yassine pasting indicators during triage.

```mermaid
sequenceDiagram
    autonumber
    participant FE as frontend
    participant IOC as ioc-collector
    participant R as Redis
    participant PG as Postgres
    FE->>IOC: POST /indicators/lookup {indicators:[{type,value}]}
    loop each indicator
        IOC->>IOC: normalize(type, value) (tip_schemas.indicators)
        IOC->>R: GET ioc:<type>:<normalized>
        alt cache hit
            R-->>IOC: cached row
        else miss
            IOC->>PG: SELECT by (type, normalized_value)
            PG-->>IOC: row (or null)
            IOC->>R: SET ioc:<...> EX 600
        end
    end
    IOC-->>FE: results (sub-200ms target)
```

Key modules: `tip_schemas.indicators.normalize` (the cross-service key),
`tip_cache` (the Redis wrapper), `services/ioc-collector/app/routes/
indicators.py`. Normalisation is what makes a defanged `example[.]com` and a
clean `example.com` resolve to the same cached entry.

## 2. The 4-step analysis cycle (the AI brain)

Triggered by the scheduler every 6h, or on demand. Returns 202, runs in
`BackgroundTasks`.

```mermaid
flowchart TD
    T["POST /analyze (202 + run_id)"] --> S1["Step 1 CVE relevance<br/>vuln CVEs + cmdb tech → ranked"]
    S1 --> S2["Step 2 Actor likelihood<br/>actors + ransomware + profile → ranked"]
    S2 --> S3["Step 3 Detection correlation<br/>Wazuh alerts + IOC DB + TTPs"]
    S3 --> S4["Step 4 Brief synthesis<br/>headline + top-3 actions + flowviz per finding"]
    S4 --> SAVE[("reports kind=analysis_cycle")]
    S1 -.fail: log+skip.-> S2
    S2 -.fail: log+skip.-> S3
    S3 -.fail: log+skip.-> S4
    SAVE --> CB["POST scheduler /internal/runs/{id}/complete"]
```

Each step is a `generate_structured` call (`ai_implementation.md`); each
step's output persists immediately (`cve_relevance`, `actor_likelihood`,
`correlations`, then `reports`). The orchestrator gathers cross-service input
via its HTTP `ContextProvider` (`context.py`) — the only fan-out service.
For each top-3 finding, it calls flowviz `POST /flows` and embeds the
returned attack flow in the report.

## 3. Flowviz attack-flow generation

```mermaid
sequenceDiagram
    autonumber
    participant C as caller (orchestrator or UI)
    participant FV as flowviz
    participant PG as flowviz.flows
    participant LL as litellm
    C->>FV: POST /flows {input}
    FV->>FV: key = sha256(input + PROMPT_VERSION)
    FV->>PG: SELECT by key
    alt cached
        PG-->>FV: stored {nodes, edges}
    else miss
        FV->>LL: chat (prompts ported from directFlowPrompts.ts)
        LL-->>FV: structured nodes+edges
        FV->>PG: store by key
    end
    FV-->>C: {nodes, edges}
```

Prompts are ported verbatim from the legacy `directFlowPrompts.ts`; output is
a Pydantic-validated ATT&CK node/edge graph; the cache key embeds
`PROMPT_VERSION` so a prompt change invalidates stale flows
(`caching_implementation.md`). The frontend renders the result with
ReactFlow + dagre.

## 4. Dorking (investigate enrichment)

The dorking feature added a search capability to indicator-intel's
investigation. Implementation: a Google Custom Search Engine primary with a
DuckDuckGo (`ddgs`) fallback when no Google key is configured.

```mermaid
flowchart TD
    INV["investigate / dork request"] --> G{"GOOGLE_CSE key?"}
    G -->|yes| GCSE["Google CSE query"]
    G -->|no / rate-limited| DDG["ddgs DuckDuckGo backend"]
    GCSE & DDG --> FIND[("dork_findings (+ dork_runs)")]
```

Verified at runtime: `example.com` → `backend=duckduckgo, 6 findings` with no
Google key present. Results persist in the `indicator` schema's `dork_runs` /
`dork_findings` tables.

## 5. Configurable notifications

The notification subsystem (orchestrator) turns platform events into
email/Telegram dispatches, filtered by analyst-configured rules.

```mermaid
sequenceDiagram
    autonumber
    participant SRC as event source (domainwatch / vuln / threat)
    participant N as orchestrator /internal/notify
    participant R as notification_rules
    participant CH as channel (SMTP / telegram)
    participant D as notification_dispatches
    SRC->>N: POST {event_type, event_ref, payload}
    N->>R: active rules WHERE event_type
    loop each rule
        N->>N: eval_filter(rule.filter, payload)
        alt matches & channel configured
            N->>CH: send
            N->>D: insert (sent/failed)
        else no match / no channel
            N->>D: insert (skipped)
        end
    end
```

Event types: `domainwatch.change`, `cve.exploited`, `threat.supply_chain`.
Filters: `severity_min`, `change_types`, `product_match`. Verified
end-to-end: a rule was created, `/internal/notify` evaluated it, and a
dispatch row was written `skipped` with "SMTP not configured" when no channel
was set — the graceful-degradation path. Modules: `app/notify/dispatcher.py`,
`app/notify/smtp.py`, `app/routes/notifications.py`.

## Cross-feature threads

All five share the platform invariants: external calls through
`fetch_with_resilience`; AI through the LiteLLM proxy with structured output;
durable results in Postgres with Redis only as accelerator; correlation IDs
threaded through every hop.
