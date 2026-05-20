# OWASP Top 10 Coverage

Mapping the platform's controls to the OWASP Top 10 (2021). Each entry
states the control and any residual gap honestly.

## A01 — Broken Access Control

- **Control:** server-side `require_permission` on every protected
  endpoint; RBAC with audited role/permission changes; session revocation
  on demotion; edge auth at the BFF; no data-service port externally
  exposed.
- **Residual:** the docker network is a trust boundary (SC3) — a host
  compromise reaches data services directly.

## A02 — Cryptographic Failures

- **Control:** passwords argon2id; refresh tokens SHA-256 hashed at rest;
  all vault secrets Fernet-encrypted; JWTs RS256 (asymmetric); service
  bootstrap tokens hashed.
- **Residual:** TLS termination is the operator's responsibility (a
  reverse proxy in front of `:3000`); in-cluster traffic is plaintext on
  the trusted bridge network.

## A03 — Injection

- **SQL injection:** all queries use SQLAlchemy parameterised statements /
  the ORM; no string-built SQL. asyncpg parameter binding throughout.
- **Command injection:** no `shell=True`/`os.system` on user input;
  ruff lint rule set includes `S` (bandit-equivalent) which flags this.
- **Prompt injection (AI):** AI reads processed data only; outputs are
  Pydantic-validated; IOCs are not auto-actioned (analyst gate). Blast
  radius is one reviewed insight (SC7).

## A04 — Insecure Design

- **Control:** the architectural principles (`04_solution_design/
  architectural_principles.md`) — schema isolation, AI off the hot path,
  single egress boundary, stale-over-blocking — are security-relevant
  design invariants, not afterthoughts.

## A05 — Security Misconfiguration

- **Control:** production guard refuses `DISABLE_AUTH=true` in production;
  `.env.example` documents the minimal config; secrets are not in compose
  or env beyond the bootstrap key.
- **Residual:** service diagnostic ports (8001–8014, 4000) are published
  by default and must be firewalled in a hardened deployment.

## A06 — Vulnerable and Outdated Components

- **Control:** dependencies pinned per-service `pyproject.toml`; slim
  official base images; LiteLLM proxy isolates services from
  provider-SDK churn. Detailed in `dependency_security.md`.
- **Residual:** no automated dependency-scanning pipeline yet (future
  work).

## A07 — Identification and Authentication Failures

- **Control:** argon2id; RS256; session revocation; 15s revocation poll;
  refresh tokens hashed + revocable.
- **Residual:** no login rate-limiting yet; no MFA (documented future
  hardening).

## A08 — Software and Data Integrity Failures

- **Control:** idempotent upserts; deterministic migrations via
  alembic-init; reproducible builds from pinned deps; AI outputs
  versioned by `prompt_version`.
- **Residual:** no image signing / SBOM generation yet.

## A09 — Security Logging and Monitoring Failures

- **Control:** structured JSON logs with correlation IDs on every line;
  audit tables (`audit_log`, `access_log`, `notification_dispatches`,
  `job_run_history`, `org_profile_versions`); diagnostic scripts
  (`smoke_test`, `check_litellm`).
- **Residual:** no centralised log aggregation / SIEM forwarding of the
  platform's *own* logs yet (it integrates with Wazuh for *external*
  alerts, not its own).

## A10 — Server-Side Request Forgery (SSRF)

- **Control:** investigation and dorking pass targets as **query
  parameters** to fixed external services (ip-api, Shodan, crt.sh, Google
  CSE, DuckDuckGo) — the service never fetches a user-supplied URL
  directly (SC6). Ingesters fetch only their named, configured feeds.
- **Residual:** adding a new source that fetches a user-controlled URL
  would re-open the vector — guarded by code review, not structurally.

## Summary

| OWASP | Coverage | Residual gap |
|---|---|---|
| A01 Access control | strong | host = trust boundary |
| A02 Crypto | strong | TLS is operator's job |
| A03 Injection | strong | — |
| A04 Insecure design | strong | — |
| A05 Misconfig | good | diagnostic ports |
| A06 Components | good | no auto scan |
| A07 AuthN | good | no rate-limit/MFA |
| A08 Integrity | good | no signing/SBOM |
| A09 Logging | strong | no self-log aggregation |
| A10 SSRF | strong | new-source review needed |
