# Services

This section documents all 15 services. The **auth service is documented
in full depth as the exemplar** because every service shares the same
skeleton (`create_service_app` factory, `_startup` wiring, JWT middleware,
routers). Reading `auth_service/` first means the other 14 documents can
focus on what is *different* about each service rather than re-explaining
the shared shape.

## The shared service skeleton

Every service's `app/main.py` follows this pattern:

```python
settings = get_settings()

async def _startup(app):
    init_engine(settings)                  # DB engine + session factory
    app.state.cache = Cache.from_url(...)  # Redis (if used)
    secrets = SecretsClient(...)           # vault client
    # fetch service-specific secrets...
    app.state.ai_client = build_ai_client(...)  # AI services only
    app.state.source_health = SourceHealthRepository(...)  # ingesters only
    await wire_auth(app, settings, name)   # (legacy) service JWT

app = create_service_app(settings, title, on_startup=[_startup], ...)
app.add_middleware(JWTAuthMiddleware, ...)
app.include_router(...)
```

A reader who internalises this once recognises it in all 15 services.

## Service catalogue

| Service | Doc | Tier | Distinguishing feature |
|---|---|---|---|
| [auth](auth_service/overview.md) | full exemplar | edge | RS256 JWT issuer, RBAC, sessions, bootstrap dance |
| [secrets](secrets_service/overview.md) | full | platform | Fernet vault, pre-auth bootstrap endpoint |
| [scheduler](scheduler_service/overview.md) | full | platform | APScheduler, sync job store, 12 jobs + watchdog |
| [news-collector](news_collector_service/overview.md) | standard | ingest | RSS/Atom, dedup by URL hash, article AI insight |
| [vuln-intel](vuln_intel_service/overview.md) | standard | ingest | NVD/EPSS/KEV, KEV backfill |
| [threat-intel](threat_intel_service/overview.md) | full | ingest | supply-chain, HIBP, multi-leg AI insight |
| [ioc-collector](ioc_collector_service/overview.md) | full | ingest | corroboration scoring, Redis hot path |
| [threat-actors](threat_actors_service/overview.md) | standard | ingest | MITRE STIX, ransomware, actor AI insight |
| [integrations](integrations_service/overview.md) | standard | analyst | Wazuh + MISP |
| [cmdb](cmdb_service/overview.md) | standard | analyst | assets + versioned profile |
| [flowviz](flowviz_service/overview.md) | standard | synthesis | ATT&CK attack-flow generator |
| [asm](asm_service/overview.md) | standard | analyst | passive attack-surface discovery |
| [domainwatch](domainwatch_service/overview.md) | standard | analyst | Playwright screenshots, change detection |
| [indicator-intel](indicator_intel_service/overview.md) | full | analyst | passive investigation + dorking |
| [orchestrator](orchestrator_service/overview.md) | full | synthesis | 4-step AI cycle, geo, /ask, notifications |

## Per-service document set

Each service directory contains at minimum:

- `overview.md` — purpose, port, schema, endpoints, dependencies,
  embedded architecture + UML Mermaid diagrams.

The "full" services additionally have dedicated UML and internal
architecture documents. The auth exemplar has the complete set
(`internal_architecture.md`, `request_flow.md`, `dependency_graph.md`,
`security_model.md`, `implementation.md`, plus `diagrams/` and `uml/`).

## UML diagram conventions

Diagrams are derived from the **actual** classes and routes — no invented
modules. Where a service has few classes (most do — they are thin route +
model + sources layers), the class diagram reflects that thinness honestly
rather than padding it.
