# Technology Choices — Overview

This chapter documents **why** each major technology was chosen, what was
rejected, and the trade-offs accepted. It is written ADR-style (decision,
context, alternatives, consequences) so a reviewer can judge the reasoning,
not just the outcome.

## The decisions at a glance

| Layer | Chosen | Principal alternatives rejected |
|---|---|---|
| Backend framework | FastAPI | Flask, Django, Express |
| Language | Python 3.11 (async) | Go, Node/TypeScript |
| HTTP client | httpx | requests, aiohttp |
| DB driver | asyncpg + SQLAlchemy 2.x async | psycopg2 (sync), Tortoise, raw SQL |
| Connection pooling | PgBouncer (transaction mode) | per-service large pools, no pooler |
| Database | PostgreSQL (schema-per-service) | DB-per-service, MySQL, Mongo |
| Cache | Redis | Memcached, in-process cache |
| AI gateway | LiteLLM proxy | per-service provider SDKs, LangChain |
| Validation/serialization | Pydantic v2 | marshmallow, dataclasses |
| Migrations | Alembic (per-service) | SQLAlchemy create_all, Django migrations |
| Scheduler | APScheduler 3.x | Celery beat, cron, Temporal |
| Frontend | Next.js 16 (App Router) | CRA/Vite SPA, Remix, plain React |
| UI kit | Ant Design 5 + Tailwind | MUI, Chakra, hand-rolled |
| Data fetching | SWR | TanStack Query, Redux Toolkit Query |
| Client state | Zustand | Redux, Context-only |
| Graph rendering | ReactFlow + dagre | D3 by hand, vis.js, cytoscape |
| Orchestration | Docker Compose | Kubernetes, Nomad, bare systemd |

## The unifying thesis

Two themes run through every choice:

1. **One async Python stack, end to end.** FastAPI → httpx → asyncpg are all
   async and compose naturally; the I/O-bound workload (feeds, downstream
   services, the LLM proxy, Postgres) is exactly what an async event loop is
   best at (`async_stack.md`).
2. **Centralise the hard, decentralise the simple.** The hard, shared
   concerns — secrets, AI egress, connection pooling, auth — are centralised
   (secrets vault, LiteLLM proxy, PgBouncer, auth service). The simple
   per-domain logic is decentralised into 15 independent services with
   isolated schemas. This is what keeps each service a thin, comprehensible
   vertical slice while the cross-cutting concerns are solved once.

## How to read the rest of the chapter

| Document | Focus |
|---|---|
| `backend_stack.md` | FastAPI + Pydantic + the language choice |
| `frontend_stack.md` | Next.js + Ant Design + SWR + Zustand + ReactFlow |
| `database_stack.md` | Postgres + asyncpg + SQLAlchemy + PgBouncer + Alembic |
| `async_stack.md` | the async runtime and why it fits the workload |
| `ai_stack.md` | LiteLLM proxy vs SDKs vs frameworks |
| `infrastructure_stack.md` | Compose, Redis, the single-host model |
| `containerization_stack.md` | Docker, uv, per-service images |
| `library_rationale.md` | the head-to-head comparisons, consolidated |

Each decision is traced back to a project requirement (`01_introduction/
objectives.md`) or an architectural principle (`04_solution_design/
architectural_principles.md`), so the choices are justified by needs, not
fashion.
