# Backend Implementation

The backend is 15 FastAPI services sharing the patterns below. This document
covers the **service-internal** mechanics: settings, routers, dependencies,
and the uniform error envelope.

## Settings — pydantic-settings, one base class

`tip_common.BaseServiceSettings` is the shared base; each service subclasses
it and adds its own fields. Settings are read from environment variables
(injected by Compose) and never hard-coded. The non-secret config — service
URLs, ports, `DISABLE_AUTH`, log level — lives here; secrets are fetched at
startup from the vault, not read from settings.

```python
class Settings(BaseServiceSettings):
    service_name: str = "vuln-intel"
    nvd_api_key: str | None = None      # populated from secrets at startup
```

The convention (`09_service-to-service`): each service reads downstream URLs
from `<NAME>_URL` env vars, so no hostname is ever hard-coded.

## Routers — thin, async, dependency-injected

Routes are grouped into `app/routes/*.py` and mounted with `include_router`.
Every handler is `async def`. The pattern:

```python
@router.get("/cves")
async def list_cves(
    q: str | None = Query(None),
    session: AsyncSession = Depends(get_session_dep),
    auth: AuthContext = Depends(require_permission("intelligence:read")),
):
    ...
```

Three dependencies recur across the codebase:

| Dependency | Provides | Defined in |
|---|---|---|
| `get_session` | a committed/rolled-back `AsyncSession` | `tip_db.session` |
| `require_permission("x:y")` | RBAC gate; returns the auth context | `tip_auth` |
| settings accessor | the service's `Settings` singleton | per-service `settings.py` |

`require_permission` is the single authorization primitive — it is how the
edge enforces RBAC. Under `DISABLE_AUTH=true` the middleware bypasses
verification, but the dependency still exists in the route signature, so
turning auth back on requires no route changes (`08_security/authorization.md`).

## The session dependency

`tip_db.get_session` wraps each request's work in a transaction with
commit-on-success / rollback-on-exception:

```python
async def get_session(factory):
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

This is why handlers never call `commit()` themselves — the dependency owns
the transaction boundary (`07_database/transactions.md`).

## Uniform error envelope

`register_error_handlers` (wired in the factory) maps the `TIPError`
hierarchy to HTTP responses with a consistent JSON shape:

| Exception | HTTP | Envelope `code` |
|---|---|---|
| `NotFoundError` | 404 | `not_found` |
| `ConflictError` | 409 | `conflict` |
| `ValidationError` | 422 | `validation_error` |
| `UpstreamError` | 502/503 | `upstream_error` |
| `TIPError` (base) | 500 | `internal_error` |

The envelope is `{"code": "...", "message": "..."}`. The frontend's BFF and
`api.ts` client read this shape uniformly (`frontend_implementation.md`).
The "auth public key not yet available" message that surfaced during the
domainwatch startup race was exactly this envelope with `code: unauthorized`.

## Per-request observability

`CorrelationIdMiddleware` assigns or propagates an `X-Correlation-ID` and
binds it to a `ContextVar` so every log line in the request — including
downstream HTTP calls made through `tip_http` — carries the same id
(`09_devops/observability.md`).

## Three runtime roles a service can play

The startup hook conditionally builds extra state depending on the service's
role:

```mermaid
flowchart LR
    BASE["every service:<br/>engine + session factory"] --> R1
    R1{"role?"}
    R1 -->|AI-consuming| AI["+ LiteLLMClient (litellm:4000)"]
    R1 -->|ingester| SH["+ SourceHealthRepository<br/>+ Cache (Redis)"]
    R1 -->|fan-out (orchestrator)| FAN["+ HTTP ContextProvider<br/>over 6 services"]
```

This is why the same factory produces a thin CRUD service (cmdb) and the
fan-out AI brain (orchestrator) — the difference is entirely in what the
startup hook attaches to `app.state`.

## Backend technology rationale

The detailed "why FastAPI / httpx / asyncpg / pydantic" rationale lives in
`12_technology_choices/backend_stack.md`. In implementation terms the
payoff is: one async stack end-to-end (ASGI → asyncpg → httpx), automatic
OpenAPI from type hints, and pydantic models doing double duty as request
validation, response serialisation, and AI structured-output schemas
(`ai_implementation.md`).
