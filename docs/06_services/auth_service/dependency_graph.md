# auth — Dependency Graph

## Build-time dependencies

From `services/auth/pyproject.toml` (shared `tip_*` libs + auth-specific):

```mermaid
graph TD
    AUTH["tip-auth-service"]
    AUTH --> COMMON["tip-common"]
    AUTH --> DB["tip-db"]
    AUTH --> SECRETS["tip-secrets"]
    AUTH --> FASTAPI["fastapi"]
    AUTH --> UVICORN["uvicorn"]
    AUTH --> SQLA["sqlalchemy + asyncpg"]
    AUTH --> ALEMBIC["alembic"]
    AUTH --> JWT["pyjwt (RS256)"]
    AUTH --> ARGON["argon2-cffi"]
    AUTH --> HTTPX["httpx (bootstrap fetch)"]
```

Notably auth does **not** depend on `tip_ai`, `tip_http`,
`tip_source_health`, or `tip_cache` — it is not an ingester, makes no AI
calls, and stores sessions in Postgres (not Redis).

## Runtime dependencies

```mermaid
graph LR
    AUTH["auth :8000"]
    AUTH -->|startup: RS256 keys + service tokens| SECRETS["secrets :8012"]
    AUTH -->|sessions, users, roles, audit| PGB[("PgBouncer -> Postgres")]
    OTHERS["all other services (legacy)"] -.->|/.well-known/jwks.json| AUTH
    BFF["frontend BFF"] -->|/login /me /users ...| AUTH
```

- **Hard runtime dependency:** secrets (at startup) and Postgres
  (continuously).
- **No runtime dependency on any data service** — auth never calls
  outward except to the vault at boot.
- **Inbound:** the BFF (user auth) and, in the legacy model, other
  services fetching the public key. Post-simplification the data services
  no longer validate JWTs, so this inbound path is dormant.

## Why this dependency shape matters

auth is intentionally a **leaf** in the service call graph (it calls only
secrets + DB). This means:

- auth can start as soon as secrets + DB are up — early in the bring-up
  order.
- A failure in any data service cannot affect auth.
- The blast radius of an auth change is bounded: it affects who can log
  in, not what any data service does internally (those trust the network).

## Failure modes

| Dependency down | Effect |
|---|---|
| secrets (at boot) | auth cannot fetch RS256 keys → fails to start (correct — no point serving without keys) |
| Postgres | login/me/refresh fail; existing tokens still validate signature but session check fails |
| secrets (after boot) | no effect — keys are already in module state |
