# Repository Layout

Each top-level directory has a single, clear responsibility. This document
walks them.

## `services/` — the 15 deployables

One folder per service, each an independent, Dockerised FastAPI app with its
own `pyproject.toml`, `Dockerfile`, `app/`, and `alembic/`.

```
services/
├── auth/  news-collector/  vuln-intel/  threat-intel/  ioc-collector/
├── threat-actors/  integrations/  cmdb/  flowviz/  asm/
├── domainwatch/  scheduler/  secrets/  indicator-intel/  orchestrator/
```

The internal anatomy of a service is standardised — see
`service_anatomy.md`.

## `packages/` — the 9 shared libraries

Path-installed into every service. Each is a proper Python package under
`src/<name>/`.

```
packages/
├── tip_common/   tip_auth/   tip_db/   tip_cache/   tip_http/
├── tip_secrets/  tip_source_health/   tip_schemas/   tip_ai/
```

Detailed in `shared_packages.md`.

## `frontend/` — the Next.js application

The UI and the BFF in one deployable (`12_technology_choices/
frontend_stack.md`). App Router pages under `src/app/`, shared components and
hooks under `src/components/` and `src/lib/`. Detailed in
`frontend_structure.md`.

## `infra/` — the deployment layer

Everything needed to bring the platform up:

```
infra/
├── docker-compose.yml          production-shape stack
├── docker-compose.dev.yml      dev overlay (bind-mounts, DISABLE_AUTH)
├── alembic-init/               one-shot migration container
├── bootstrap/                  seed_secrets.py, smoke_test.py, check_litellm.py, …
├── pgbouncer/                  pgbouncer.ini
└── litellm/                    proxy config
```

Detailed in `infra_structure.md`.

## `prompt/` — the specification (source of truth)

Holds `prompt.md` (the full spec every design decision derives from) and
`credentials.env` (the exact secret names `seed_secrets.py` reads). This
directory is **untouched** — it is the requirement input, not an artifact.

## `AvailableServices/` — legacy source for refactors

The original standalone projects (Flowviz, ASM, Domain Watcher) that were
refactored into the `flowviz`, `asm`, and `domainwatch` services. Kept as the
reference for what was ported vs. discarded (`06_services` refactor notes).
Not deployed; not part of the running platform. (Its only `test_*.py` files
live here — legacy, not the platform's tests — see `11_testing`.)

## `OpenAPI/` — API contract snapshots

Per-service `openapi.json` files, the machine-readable API contract the
frontend types track by hand (`10_implementation/api_implementation.md`).

## `screenshots/` — the visual test + report artifact

`walkthrough.py` (the Playwright walkthrough) and the 40+ numbered PNGs it
produces (`11_testing/playwright_testing.md`).

## `docs/` — this documentation suite

The 17-section suite. Self-describing.

## Root files

| File | Role |
|---|---|
| `CLAUDE.md` | living architecture/build notes (the per-service catalog) |
| `Makefile` | operator commands (`up`, `seed`, `migrate`, `smoke-test`, …) |
| `pyproject.toml` | root tooling only — ruff + mypy config |
| `.env.example` | template for the two root secrets + bootstrap params |

The root `pyproject.toml` deliberately holds **only tooling config**, not
dependencies — dependencies live per-service and per-package, so the root is
the lint/type contract for the whole tree (`11_testing/static_analysis.md`).
