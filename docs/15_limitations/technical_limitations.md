# Technical Limitations

## L1 — No automated unit or integration test suite

**The limitation.** There are no `pytest` unit or integration tests in
`packages/` or `services/` (`11_testing/testing_strategy.md`). The only
`test_*.py` files are legacy code under `AvailableServices/`.

**Why.** Single developer, fixed timeline; behaviour was validated against
live upstream data; `mypy --strict` was leaned on as the signature/shape net.

**Mitigation.** Static analysis (mypy strict + ruff), smoke tests, manual E2E
blocks, and the Playwright walkthrough together form a broad-but-shallow net
(`11_testing/coverage.md`).

**Residual risk.** Logic that type-checks, boots, and renders but is subtly
wrong — especially in `normalize` and confidence scoring — is caught only by
a human. **Remedy:** `16_future_work` (unit tranche, prioritising the pure
high-risk functions).

## L2 — No performance benchmarks

**The limitation.** No load test, latency histogram, or throughput
measurement was captured (`13_performance/benchmarks.md`). The headline
sub-200ms IOC lookup is a **design target**, not a measured result.

**Why.** Low-volume internal-tool scope; correctness was prioritised over
performance characterisation.

**Mitigation.** Per-call `duration_ms` is already logged
(`09_devops/observability.md`), so the data is capturable; the architecture's
latency budget is reasoned (`13_performance/overview.md`).

**Residual risk.** The hot-path target is unverified. **Remedy:** a k6/Locust
baseline (`16_future_work`).

## L3 — Frontend type drift

**The limitation.** Frontend types (`src/types/`) are maintained by hand
against the backend OpenAPI; there is no codegen, so they can drift from the
real API shapes (`10_implementation/api_implementation.md`).

**Why.** No type-generation step was wired.

**Mitigation.** The Playwright walkthrough surfaces runtime shape mismatches
as render errors (`11_testing/playwright_testing.md`); `OpenAPI/` snapshots
exist as the contract.

**Residual risk.** A backend response-shape change can silently mismatch the
frontend type until a page breaks. **Remedy:** OpenAPI-to-TypeScript codegen
in CI (`16_future_work`).

## L4 — Scheduler is a singleton

**The limitation.** The scheduler cannot be horizontally replicated — two
instances would double-fire jobs (`13_performance/scalability.md`).

**Why.** APScheduler 3.x runs in-process against a shared job store; it has no
leader election.

**Mitigation.** A single scheduler is sufficient for the workload; the
watchdog catches stalls.

**Residual risk.** The scheduler is a single point of failure for *triggering*
(not for data — ingestion endpoints can be called manually). **Remedy:**
leader election or a scheduler with native clustering (`16_future_work`).

## L5 — Dual database engines in the scheduler

**The limitation.** The scheduler runs a synchronous psycopg2 engine
alongside the async one, purely for APScheduler's sync job store
(`12_technology_choices/async_stack.md`).

**Why.** APScheduler 3.x's job store is sync-only; APScheduler 4 is async but
beta.

**Mitigation.** Isolated to one service; job-store writes are infrequent, so
the performance impact is negligible.

**Residual risk.** Minor architectural inconsistency. **Remedy:** migrate when
APScheduler 4 stabilises (`16_future_work`).

## L6 — JSONB can hide unindexed access

**The limitation.** Heavy use of `JSONB` (`raw`, `payload`, `details`) means a
query against an unpromoted JSON field would not use an index.

**Why.** JSONB stores the full upstream record by design
(`07_database/optimization.md`).

**Mitigation.** Every field the platform actually filters on is promoted to a
real, indexed column; JSONB holds only the unqueried remainder.

**Residual risk.** A future feature querying a JSON-only field would be slow
until that field is promoted/indexed. **Remedy:** promote-and-index as access
patterns evolve (`07_database/indexing_strategy.md`).

## Summary

| ID | Limitation | Severity | Remedy in §16 |
|---|---|---|---|
| L1 | No unit/integration tests | high | unit + integration tranches |
| L2 | No benchmarks | low–medium | k6/Locust baseline |
| L3 | Frontend type drift | low | OpenAPI codegen |
| L4 | Scheduler singleton | medium | leader election |
| L5 | Dual engines (scheduler) | low | APScheduler 4 |
| L6 | JSONB unindexed risk | low | promote-and-index |
