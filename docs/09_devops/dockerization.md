# Dockerization

## Why containers at all

Containerisation is not decoration here — it solves concrete problems for
this platform:

| Need | Without containers | With containers |
|---|---|---|
| **Consistency** | "works on my machine" across 15 services + Python versions | one image = one identical runtime everywhere |
| **Dependency isolation** | 15 services' deps collide in one venv | each service's deps isolated in its image |
| **Reproducibility** | manual install order, drift | `make up` rebuilds identical stack |
| **Portability** | tied to host's Python/libs | runs on any Docker host |
| **Operational simplicity** | start 15 processes by hand | one compose file |
| **Bring-up ordering** | manual sequencing | `depends_on` conditions |

For a 15-service platform a bank's ops team must run, containerisation is
the difference between a one-command deployment and a runbook of fifteen
`systemd` units with hand-managed dependencies.

## Per-service image structure

Each `services/<name>/Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
# shared libraries first (better layer caching)
COPY packages/ /app/packages/
COPY services/<name>/ /app/service/
RUN pip install uv && uv pip install --system -e /app/service
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80xx"]
```

The shared `packages/` are copied and path-installed via the service's
`pyproject.toml` (`tip-common = { path = "../../packages/tip_common" }`).

## Special images

| Image | Base | Why |
|---|---|---|
| domainwatch | `mcr.microsoft.com/playwright/python` | ships browser binaries (no fragile runtime install) |
| litellm | `ghcr.io/berriai/litellm` | official AI gateway |
| alembic-init | python-slim + all packages | needs every `app.models` to migrate |

## Layer caching strategy

Copying `packages/` before the service code means a service-code change
does not invalidate the (slow) dependency-install layer — only the final
copy + install of the changed service. This keeps incremental rebuilds
fast, which mattered during development (the deploy scripts rebuild only
the changed services).

## The two compose files

| File | Role |
|---|---|
| `infra/docker-compose.yml` | production-shape: built images, healthchecks, depends_on |
| `infra/docker-compose.dev.yml` | overlay: bind-mounts `packages/` for live editing, `DISABLE_AUTH=true`, debug logging |

## Build commands

```bash
make build     # docker compose build (all services)
# or per-service during development:
docker compose -f infra/docker-compose.yml --env-file .env build <service>
docker compose -f infra/docker-compose.yml --env-file .env up -d --force-recreate <service>
```

The development workflow rebuilt and recreated only the services that
changed in each iteration — the per-service image isolation makes this
fast.

## What is NOT containerised

- The `.env` file (host-managed).
- The operator's backups of `postgres-data`.
- TLS termination (a production reverse proxy, outside the compose).

## Image count and footprint

~20 containers at runtime (15 services + postgres + pgbouncer + redis +
litellm + frontend), plus two transient one-shot sidecars
(alembic-init, bootstrap-seed). The Python service images are light; the
heaviest is domainwatch (Playwright browser). Total footprint is sized for
a single mid-range Linux host (`05_architecture/infrastructure_topology.md`).
