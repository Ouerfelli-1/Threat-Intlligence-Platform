# Request Lifecycle

This document traces representative requests end to end, from the
browser keystroke to the rendered result, naming the real code at each
hop.

## Lifecycle A — IOC lookup (the hot path)

The latency-critical path. Target: < 200 ms.

```mermaid
sequenceDiagram
    autonumber
    participant U as Yassine (browser)
    participant API as frontend api.ts
    participant BFF as BFF /api/[...path]
    participant IOC as ioc-collector :8004
    participant R as Redis
    participant PG as Postgres (via PgBouncer)

    U->>API: type IP, press Enter
    API->>API: read token from Zustand store
    API->>BFF: POST /api/indicators/lookup (Bearer)
    BFF->>IOC: POST /indicators/lookup
    IOC->>R: GET ioc:ip:8.8.8.8
    alt cache hit
        R-->>IOC: cached verdict
    else cache miss
        IOC->>PG: SELECT ... WHERE type, normalized_value
        PG-->>IOC: row or null
        IOC->>R: SETEX ioc:ip:8.8.8.8 (10 min TTL)
    end
    IOC-->>BFF: 200 verdict
    BFF-->>API: 200
    API-->>U: render result card
```

Key code:
- `frontend/src/lib/api.ts` — token attach, single-flight 401 redirect.
- `frontend/src/app/api/[...path]/route.ts` — `indicators` → ioc-collector.
- `services/ioc-collector/app/routes/indicators.py` — lookup with Redis
  first.

## Lifecycle B — Generate a threat insight (AI multi-leg)

The richest path: three AI legs + an inline sibling call + IOC
auto-promotion + cache-first.

```mermaid
sequenceDiagram
    autonumber
    participant U as Amira
    participant BFF
    participant TI as threat-intel :8003
    participant L as LiteLLM :4000
    participant FV as flowviz :8008
    participant IOC as ioc-collector :8004
    participant PG as Postgres

    U->>BFF: POST /api/threats/{id}/analyze
    BFF->>TI: POST /threats/{id}/analyze
    TI->>PG: SELECT threat_insights (cache-first)
    alt cached at current prompt_version and not force
        PG-->>TI: existing insight
        TI-->>BFF: 200 (no AI call)
    else generate fresh
        TI->>L: IOC extraction (leg 1)
        L-->>TI: extracted IOCs
        TI->>L: hunting hypothesis (leg 2)
        L-->>TI: hypothesis + wazuh rule + TTPs
        TI->>FV: POST /flows (leg 3 — attack flow)
        FV->>L: generate ATT&CK graph
        L-->>FV: nodes/edges
        FV-->>TI: attack flow
        TI->>IOC: POST /indicators (auto-promote extracted IOCs)
        TI->>PG: upsert threat_insights (prompt_version)
        TI-->>BFF: 200 full insight
    end
    BFF-->>U: render InsightView
```

Key code:
- `services/threat-intel/app/routes/threats.py` — cache-first guard,
  serialised legs (EC11), lossless merge, auto-promotion.
- `services/flowviz/app/routes/flows.py` — cached by
  `sha256(input + prompt_version)`.

## Lifecycle C — Daily executive brief (scheduled, multi-service)

No user in the loop — the scheduler drives it.

```mermaid
sequenceDiagram
    autonumber
    participant SCH as scheduler
    participant ORCH as orchestrator
    participant SRC as vuln/actors/integrations/cmdb
    participant L as LiteLLM
    participant PG as Postgres

    SCH->>ORCH: POST /analyze {run_id}
    ORCH-->>SCH: 202 running
    Note over ORCH: step 1 CVE relevance
    ORCH->>SRC: fan-out (CVEs + tech stack)
    ORCH->>L: rank -> cve_relevance
    Note over ORCH: step 2 actor likelihood
    ORCH->>SRC: actors + ransomware victims + profile
    ORCH->>L: rank -> actor_likelihood
    Note over ORCH: step 3 correlation
    ORCH->>SRC: Wazuh alerts + IOC DB + TTPs
    ORCH->>L: correlate -> correlations
    Note over ORCH: step 4 brief synthesis
    ORCH->>L: synthesize headline + top-3 actions
    ORCH->>PG: insert reports(kind=analysis_cycle)
    ORCH->>SCH: POST /internal/runs/{run_id}/complete
```

Key code:
- `services/scheduler/app/jobs.py` — `orchestrator_analysis` job.
- `services/orchestrator/app/analysis.py` — `run_analysis_cycle`.
- Per-step failure is logged and skipped; the cycle continues (G2).

## Lifecycle D — Login + session

```mermaid
sequenceDiagram
    autonumber
    participant U as user
    participant LP as /login page
    participant BFF
    participant AUTH as auth :8000
    participant PG as Postgres

    U->>LP: username + password
    LP->>BFF: POST /api/login
    BFF->>AUTH: POST /login
    AUTH->>PG: verify password (argon2)
    AUTH->>PG: insert session
    AUTH-->>BFF: {access_token, refresh_token}
    BFF-->>LP: tokens
    LP->>LP: store token in Zustand (persist)
    LP->>BFF: GET /api/me (Bearer)
    BFF->>AUTH: GET /me (validates JWT, checks session not revoked)
    AUTH-->>LP: {id, username, role, permissions}
    Note over LP: layout polls /me every 15s for revocation
```

Key code:
- `frontend/src/app/login/page.tsx`, `frontend/src/lib/store.ts`.
- `services/auth/app/routes/auth.py` — `/login`, `/me` (DB-truth session
  check), `frontend/src/app/(app)/layout.tsx` — 15s `/me` poll.

## Cross-cutting middleware (every request)

Every request to every service passes through, in order:

```mermaid
flowchart LR
    REQ[Request] --> CID[correlation-id middleware<br/>tip_common]
    CID --> JWT[JWTAuthMiddleware<br/>tip_auth — no-op if DISABLE_AUTH]
    JWT --> PERM[require_permission dep<br/>per route]
    PERM --> H[route handler]
    H --> ERR[error handlers<br/>tip_common]
    ERR --> RESP[JSON response + X-Correlation-ID]
```

- **Correlation ID** — generated or propagated via `X-Correlation-ID`,
  logged on every line.
- **JWTAuthMiddleware** — validates the bearer token (or short-circuits
  to a dev-admin context when `DISABLE_AUTH=true`).
- **require_permission** — per-route RBAC dependency.
- **Error handlers** — convert exceptions (`NotFoundError`, validation,
  AI errors) into typed JSON responses.

## Latency budget by lifecycle

| Lifecycle | Dominant cost | Target / typical |
|---|---|---|
| A — IOC lookup | Redis round-trip | < 200 ms (cache hit ≈ single-digit ms) |
| B — threat insight (fresh) | 2–3 AI legs + flowviz | 30–95 s (provider-bound) |
| B — threat insight (cached) | one Postgres read | < 1 s (measured ~0.1–0.2 s) |
| C — daily brief | 4 AI calls + fan-out | minutes (background, no user waiting) |
| D — login | argon2 verify + session insert | sub-second |

The only lifecycle a user waits on synchronously and which can be slow is
**B-fresh**, and it is explicitly cached so the second view is **B-cached**.
