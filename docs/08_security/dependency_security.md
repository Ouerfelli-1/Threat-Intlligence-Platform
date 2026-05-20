# Dependency Security

## Pinning strategy

Each service declares its dependencies in its own `pyproject.toml` with
version floors (`>=`) and path-installed shared libraries. The shared
`tip_*` packages are pinned by path, so a shared-library change is
versioned with the repository, not floated from an index.

## Dependency surface per tier

| Tier | Key dependencies |
|---|---|
| Web | fastapi, uvicorn, pydantic |
| DB | sqlalchemy, asyncpg, alembic, psycopg2 (scheduler only) |
| HTTP | httpx |
| Auth | pyjwt, argon2-cffi |
| AI | the LiteLLM client path (services hold no provider SDKs) |
| Service-specific | feedparser (news), stix2 (actors), ddgs (indicator-intel), aiosmtplib (orchestrator), playwright (domainwatch) |

## The LiteLLM isolation benefit

Data services do **not** import the OpenAI / Anthropic / GitHub Models
SDKs. They talk to the LiteLLM proxy over plain HTTP. This means:

- Provider-SDK vulnerabilities affect one container (litellm), not 15.
- Upgrading a provider SDK is a litellm rebuild, not a platform-wide
  dependency bump.
- A compromised provider SDK's blast radius is the proxy, which holds no
  business data.

## Base image strategy

- Most services: official slim Python base images.
- domainwatch: `mcr.microsoft.com/playwright/python` (official Microsoft
  image with browser binaries) — chosen over installing browsers at
  runtime, which is both slower and a larger supply-chain surface.
- litellm: the official `ghcr.io/berriai/litellm` image.

Official, minimal bases reduce the package surface that could carry a
vulnerability.

## Lint-level security checks

The root `pyproject.toml` ruff configuration includes the `S` rule set
(bandit-equivalent), which flags common security anti-patterns
(`shell=True`, hardcoded passwords, insecure temp files) at lint time.
`ASYNC` rules catch blocking calls in async code. `S101` (assert) is
ignored only in tests.

## Known gaps (honest)

| Gap | Status | Future |
|---|---|---|
| Automated dependency scanning (Dependabot / pip-audit) | not configured | CI integration |
| SBOM generation | not produced | future |
| Image signing (cosign) | not done | future |
| Lockfiles (exact pins) | floors only (`>=`) | could pin exact via uv lock |

These are documented in `16_future_work/security_improvements.md`. At the
current stage the controls are: pinned floors, official slim bases, the
LiteLLM isolation, and lint-time bandit checks.

## The frontend dependency surface

The Next.js frontend pins its dependencies in `frontend/package.json` with
a committed `package-lock.json`. The lockfile is the exact-version pin
that the Python side defers. Key dependencies: next 16, react 19, reactflow
+ dagre (attack-flow rendering), swr (data fetching), zustand (state).
