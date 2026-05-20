# Stakeholders

## Direct users

### Yassine — SOC Analyst

- **Goal during a shift.** Triage alerts. When an IP / domain / hash
  surfaces in a Wazuh alert, decide *malicious / benign / unknown* in
  under 10 seconds.
- **Surfaces used.** `/iocs/lookup` (single + bulk paste),
  `/iocs/investigate` for unknowns, `/integrations/wazuh` for the
  source alert.
- **Tolerance for friction.** Very low. If the lookup takes > 1 second
  Yassine will paste into VirusTotal instead. This is why the IOC hot
  path runs through Redis (`ioc:<type>:<value>` 10-minute TTL,
  `services/ioc-collector/app/routes/indicators.py` lookup).
- **Authority.** Cannot delete actors or change feed configuration; can
  mark indicators relevant/not-relevant.
- **RBAC role.** `analyst`.

### Amira — TI Analyst

- **Goal during a day.** Curate the intelligence library. Run AI
  analysis on the day's new threats, vet the auto-generated Wazuh rules,
  promote IOCs from threat insights into the central library.
- **Surfaces used.** `/intelligence/articles`, `/intelligence/threats`,
  `/intelligence/supply-chain`, `/actors`, `/iocs`, `/operations/reports`.
- **Tolerance for friction.** Moderate. Will accept a 30-second AI
  analysis but expects the result to be saved so re-opening doesn't
  re-run.
- **Authority.** Mark anything relevant / escalated / not-relevant;
  create manual actors and IOCs; override AI insights; trigger
  re-analysis.
- **RBAC role.** `analyst` (with future-room for an `editor` super-role).

### Karim — Security Manager

- **Goal during a day.** Open the dashboard once at 09:00. Read the
  Daily Threat Briefing and the Geopolitical Insights card. Skim the
  top-ranked actors. Leave.
- **Surfaces used.** `/` (dashboard only).
- **Tolerance for friction.** Highest. Will not click into anything
  except the brief itself.
- **Authority.** Read-only on data; write on the company profile.
- **RBAC role.** `viewer` with `profile:write`.

## Indirect stakeholders

### The bank's compliance officer

Cares about:

- **Audit trail.** Every login → `auth.audit_log`. Every secret read →
  `secrets.access_log`. Every notification dispatch →
  `orchestrator.notification_dispatches`. Every profile change →
  `cmdb.org_profile_versions` + `cmdb.profile_change_log`.
- **Egress visibility.** Only the LiteLLM proxy and the named
  ingester sources should be making outbound HTTPS calls. The compose
  file is the inventory.
- **Data residency.** Postgres + Redis + screenshots stay on the host.
  AI calls are scoped to whatever the operator configures on the
  LiteLLM proxy (the operator chooses GitHub Models, OpenAI, Anthropic,
  Bedrock, etc.).

### The bank's IT operations team

Cares about:

- **Single command bring-up** after a server reboot — `make up`.
- **Single command diagnostic** when something feels slow —
  `make check-llm` (AI chain) or `make smoke-test` (all services).
- **No surprise dependencies.** Every service is a Python image with a
  pinned `pyproject.toml`; no `pip install` at runtime.

### The bank's network / firewall team

Cares about:

- **Outbound destinations.** The CISA, NVD, abuse.ch, OTX, ransomware.live,
  HIBP, Shodan, Wazuh, MISP endpoints (configured per-service) — these
  must be allowlisted on the egress firewall.
- **No inbound NAT** beyond the frontend (3000) and optionally a 443
  reverse proxy.

## Engineering / build stakeholders

### The developer (the author)

Cares about:

- **Service-level isolation** for fast iteration. Each service has its
  own `pyproject.toml` and Dockerfile, so changing one service rebuilds
  only that image.
- **Single source of truth for shared logic** — the `packages/tip_*`
  libraries, installed via path dependencies in every service's
  `pyproject.toml`.
- **No hidden state.** Every secret lives in the `secrets` vault; the
  `.env` file holds only the bootstrap key.

### Future maintainers

Cares about:

- **Stable per-service schemas.** Cross-service references use stable
  IDs (CVE-IDs, MITRE technique IDs, normalised indicator values) —
  *never* surrogate FKs across schemas. Adding or splitting a service
  doesn't require a database-wide migration.
- **Documented engineering decisions.** This `docs/` tree.
- **Clear extension points.** New AI policies via the orchestrator
  `ai_policies` table; new ingest sources via per-service `sources/`
  modules.

## Adversaries (negative stakeholder)

The threat model documents these in `08_security/threat_model.md`. The
short summary:

- **External attacker without credentials** — only the frontend port is
  exposed; auth gates everything; the BFF re-validates JWTs on every
  request through the auth service.
- **Internal attacker with shell on one service** — every service has
  the smallest possible secret set; the secrets vault encrypts everything
  with `FERNET_KEY` which is the one and only thing the operator must
  protect outside the vault.
- **Supply-chain attacker** — all dependencies pinned in
  `pyproject.toml`; the AI gateway (LiteLLM) shields services from
  upstream-provider compromise.
