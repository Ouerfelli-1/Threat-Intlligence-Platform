# Security Limitations

These are stated plainly. The platform's security posture is strong at the
edge (`08_security`) but has explicit, deliberate gaps documented here.

## L13 — Inter-service authentication is disabled

**The limitation.** Data services run with `DISABLE_AUTH=true`; JWT validation
happens only at the frontend↔BFF edge, not between services
(`10_implementation/runtime_behavior.md`).

**Why.** A deliberate operator decision: the services run only on the internal
Docker network, nothing but the frontend port is published, so inter-service
auth was judged unnecessary complexity (`08_security/attack_surface_
analysis.md`). It also resolved a startup race ("auth public key not yet
available") and a logout cascade.

**Mitigation.** Network isolation — the services are unreachable from outside
the host; only the frontend (3000) is exposed. The full inter-service auth
wiring (`wire_auth`, `obtain_service_jwt`, lazy-key middleware) still exists
and re-enables by flipping `DISABLE_AUTH=false`.

**Residual risk.** An attacker who achieves code execution *inside* the Docker
network could call any service unauthenticated. This is the classic
"hard shell, soft interior" trade. **Remedy:** re-enable inter-service JWTs
for a defence-in-depth posture (`16_future_work`); the capability is dormant,
not deleted.

## L14 — Default admin password

**The limitation.** The bootstrap admin password defaults to `changeme`
(`11_testing/test_data_and_fixtures.md`).

**Why.** A known dev/test fixture credential so the walkthrough and E2E blocks
can authenticate.

**Mitigation.** Documented as must-rotate-after-first-login; it is a seed
default, not a hardcoded production credential.

**Residual risk.** If a deployment ships without rotating it, the admin
account is trivially guessable. **Remedy:** force a password change on first
login (`16_future_work`).

## L15 — One `FERNET_KEY` protects the whole vault

**The limitation.** The entire secrets vault is encrypted with a single
`FERNET_KEY` held in `.env`; compromising it compromises every secret
(`08_security/secrets_management.md`).

**Why.** Simplicity — one key the operator must protect, by design.

**Mitigation.** The threat model explicitly names `FERNET_KEY` as the one
thing the operator must guard outside the vault; access to every secret is
logged in `secrets.access_log`.

**Residual risk.** Single-key blast radius; rotation is a manual re-encrypt.
**Remedy:** envelope encryption / a managed KMS (`16_future_work`).

## L16 — No rate limiting at the edge by default

**The limitation.** While `rl:*` rate-limit infrastructure exists in Redis,
there is no comprehensive per-user/edge rate limiting enforced across all
endpoints.

**Why.** Internal-tool scope with a known, small user base.

**Mitigation.** The platform is not internet-facing; the BFF is the single
ingress; the user base is the three personas plus admins.

**Residual risk.** A compromised internal client could issue unbounded
requests. **Remedy:** edge rate limiting on the BFF (`16_future_work`).

## L17 — No automated dependency / image scanning

**The limitation.** Dependencies are pinned but not scanned by an automated
tool (e.g. `pip-audit`, Trivy) in any pipeline
(`08_security/dependency_security.md`).

**Why.** No CI to run a scanner in (L7).

**Mitigation.** Dependencies are pinned per service; ruff's bandit (`S`) lints
catch in-code security smells.

**Residual risk.** A known-vulnerable dependency could go unnoticed.
**Remedy:** `pip-audit` + Trivy in CI (`16_future_work`).

## Summary

| ID | Limitation | Severity | Remedy in §16 |
|---|---|---|---|
| L13 | Inter-service auth disabled | medium | re-enable service JWTs |
| L14 | Default admin password | low | force first-login change |
| L15 | Single `FERNET_KEY` | medium | envelope/KMS |
| L16 | No edge rate limiting | low–medium | BFF rate limit |
| L17 | No dependency/image scanning | medium | pip-audit + Trivy in CI |

The honest framing: the platform is **well-secured against the external
threat it actually faces** (only the frontend is exposed; the edge enforces
RS256 JWT + RBAC; secrets are encrypted and access-logged) and **deliberately
relaxed on internal defence-in-depth** (L13) for operational simplicity on an
isolated host. The trade is reasonable for the deployment context and
reversible by design.
