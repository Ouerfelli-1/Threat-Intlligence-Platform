# TIP Platform — Engineering Documentation

This directory contains the complete engineering documentation for the
**Threat Intelligence Platform (TIP)** — a 15-service Python micro-services
architecture, a Next.js 16 frontend, and the supporting infrastructure that
glues them into a single deployable system.

The documentation is intended for four audiences:

| Audience | Entry point |
|---|---|
| **Thesis / defence reviewer** | `01_introduction/` → `04_solution_design/` → `05_architecture/global_architecture.md` |
| **Architecture reviewer** | `05_architecture/` then `06_services/<service>/internal_architecture.md` |
| **Security auditor** | `08_security/` cross-referenced with `06_services/auth_service/security_model.md` |
| **New engineer onboarding** | `14_project_structure/repository_layout.md` → service of interest |

## Layout

```
docs/
├── README.md                       ← you are here
├── 01_introduction/                business + technical context
├── 02_problem_statement/           what we solved and why
├── 03_existing_solutions/          why we did not buy COTS
├── 04_solution_design/             our high-level decisions
├── 05_architecture/                topology, request lifecycle, deployments
├── 06_services/                    per-service deep dives (15 services)
├── 07_database/                    schema/per-service strategy, indexes
├── 08_security/                    auth, RBAC, OWASP coverage, secrets vault
├── 09_devops/                      containers, compose, smoke tests, runbooks
├── 10_implementation/              how features were actually built
├── 11_testing/                     QA strategy + Playwright walkthrough
├── 12_technology_choices/          framework + library rationale
├── 13_performance/                 cache strategy, AI quota, latency notes
├── 14_project_structure/           repo layout + startup sequence
├── 15_limitations/                 honest tradeoffs
├── 16_future_work/                 evolution plan
└── 17_conclusion/                  what was delivered
```

## Conventions used throughout the documentation

- **Mermaid** for every diagram. Render natively in GitHub / GitLab / VS Code preview.
- **Code references** are full repo-relative paths (e.g. `services/auth/app/routes/users.py:45`)
  so the reader can jump straight from claim to source.
- **Measured vs inferred** is always called out. Numbers prefixed with
  *"Measured:"* came from a real run; *"Estimated:"* is a reasoned
  upper/lower bound from architecture.
- **No marketing language.** Statements are sourced from the implementation
  or marked as design intent.

## Source-of-truth files outside `docs/`

| File | Why it matters |
|---|---|
| `CLAUDE.md` | Operational playbook + per-service one-liner reference. |
| `prompt/prompt.md` | Original product specification — referenced where design intent is contested. |
| `infra/docker-compose.yml` | Authoritative service topology. |
| `services/*/alembic/versions/*.py` | Schema source of truth (no `models.py`-only assertions). |
| `screenshots/` | 40 Playwright-captured UI shots used as figures throughout. |

## How this documentation was produced

A static analysis pass over the repository, supplemented by direct reading
of every `pyproject.toml`, `Dockerfile`, `alembic/versions/*.py`, `main.py`,
and the compose file. Every architecture diagram was derived from the
actual file layout and import graph — not generated from a template.
