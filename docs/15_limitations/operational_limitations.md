# Operational Limitations

## L7 — No CI/CD pipeline

**The limitation.** No `.github/workflows`, no GitLab CI, no Jenkins. Builds,
tests, and deploys are run by hand (`09_devops/ci_cd.md`).

**Why.** Single developer, single host; effort went to the platform itself.

**Mitigation.** Every stage's command already exists and is exit-code-correct
(`ruff`, `mypy`, `smoke_test.py`, `check_litellm.py`), so the gap is wiring,
not capability.

**Residual risk.** No automated gate prevents a regression from being
deployed; deploy-time human error is possible. **Remedy:** the phased
pipeline in `11_testing/ci_test_automation.md` and `16_future_work` — phase 1
(ruff+mypy in CI) is near-zero effort.

## L8 — Single host, no high availability

**The limitation.** All ~20 containers run on one Linux host; the host is a
single point of failure (`12_technology_choices/infrastructure_stack.md`).

**Why.** One finance-enterprise tenant, SOC-tool workload, one operator —
multi-host HA was out of scope.

**Mitigation.** `restart: unless-stopped` survives process/host reboot; the
schema-per-service + URL-discovery design makes a multi-host split a
configuration change, not a rewrite (`13_performance/scalability.md`).

**Residual risk.** Host failure takes the platform down until restored.
**Remedy:** Kubernetes migration (`16_future_work`).

## L9 — No automated backups

**The limitation.** There is no scheduled backup of the `postgres-data`
volume in the repository (`09_devops/rollback_strategy.md`). Postgres holds
all business data **and** the secrets vault.

**Why.** Backups are listed as operator-managed and outside the compose file;
no backup job was implemented.

**Mitigation.** A periodic off-host `pg_dump` is *recommended* in the docs.

**Residual risk.** This is the most serious operational gap: a corrupting
migration or volume loss with no backup is unrecoverable. **Remedy:** an
automated `pg_dump` cron to off-host storage (`16_future_work`), called out
as high priority.

## L10 — No metrics/monitoring/alerting stack

**The limitation.** No Prometheus, Grafana, Alertmanager, or centralised log
store (`09_devops/monitoring.md`).

**Why.** Single-host scope; application-level surfaces were judged sufficient.

**Mitigation.** Rich application surfaces exist: `/health`, `/health/sources`,
`job_run_history`, structured JSON logs with correlation IDs, and the
notification subsystem for event alerting.

**Residual risk.** No real-time metric alerting (e.g. latency/CPU); failures
are seen via logs and health endpoints, not a dashboard or page. **Remedy:** a
Prometheus + Grafana + Loki stack reading the already-structured logs and
`/health/sources` (`16_future_work`).

## L11 — Manual deploy and rollback

**The limitation.** Deploys and rollbacks are manual SSH + `git pull` +
`compose build/up` sequences; rollback is git-revert-and-rebuild because there
is no image registry (`09_devops/deployment_strategies.md`,
`rollback_strategy.md`).

**Why.** No registry, no pipeline.

**Mitigation.** Per-service image isolation makes both fast and low-blast-
radius; the git history is a clean rollback ledger.

**Residual risk.** No instant image re-pull; destructive-migration rollback
requires care. **Remedy:** an image registry + CD deploy stage
(`16_future_work`).

## L12 — No secret rotation automation (beyond bootstrap tokens)

**The limitation.** Rotating provider keys or `FERNET_KEY` is manual; only the
bootstrap-token rotation in the auth/secrets dance is automated
(`08_security/secrets_management.md`).

**Why.** Out of scope for the timeline.

**Mitigation.** The LiteLLM proxy means rotating a provider key is a single
proxy restart, not a fleet redeploy.

**Residual risk.** `FERNET_KEY` rotation is a manual re-encrypt step; provider
keys do not rotate on a schedule. **Remedy:** a rotation procedure/job
(`16_future_work`).

## Summary

| ID | Limitation | Severity | Remedy in §16 |
|---|---|---|---|
| L7 | No CI/CD | medium | phased pipeline |
| L8 | Single host / no HA | medium | Kubernetes |
| L9 | No automated backups | **high** | `pg_dump` cron (priority) |
| L10 | No metrics/alerting stack | medium | Prometheus/Grafana/Loki |
| L11 | Manual deploy/rollback | medium | registry + CD |
| L12 | No secret rotation | low–medium | rotation job |
