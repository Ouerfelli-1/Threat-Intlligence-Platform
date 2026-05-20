# Security Challenges

The platform handles sensitive intelligence and integrates with the bank's
SIEM. This document frames the security problems; the full treatment is in
`08_security/`.

## SC1 — Credential sprawl across 15 services

Each service needs different secrets (NVD key, abuse.ch key, Wazuh creds,
MISP key, OpenRouter / GitHub provider keys, SMTP creds). Storing these in
15 `.env` files or in the compose file would scatter secrets and make
rotation a multi-file change.

**Response:** a dedicated **secrets vault** service
(`services/secrets/`). Everything is Fernet-encrypted at rest. Only
`FERNET_KEY` and `SECRETS_BOOTSTRAP_TOKEN` stay in `.env`. Every secret
read is logged to `secrets.access_log` (who read `OPENROUTER_API_KEY` and
when). Rotation is a single vault write.

## SC2 — The bootstrap chicken-and-egg

Services need secrets to start, but cannot authenticate (get a JWT)
without first reading secrets. A naive design either hard-codes a
super-credential or leaves the vault open.

**Response:** a scoped pre-auth endpoint
`secrets /internal/bootstrap-fetch` authorised by the shared
`SECRETS_BOOTSTRAP_TOKEN`. It is the *only* unauthenticated vault path and
returns single secrets by name. Once a service is up it could use a JWT
for `GET /secrets/{name}`, but in the simplified-auth deployment it
continues using the bootstrap token on the trusted docker network.

## SC3 — Authentication boundary placement

Where should authentication be enforced? On every service (defence in
depth, but operationally fragile — see OC5's 24-hour 401 cascade) or at
the edge (simpler, but the docker network must be trusted)?

**Response (commit `5d216c1`):** auth is enforced at the **browser ↔ BFF**
edge. The `auth` service keeps full JWT validation for its own endpoints
(`/me`, `/users`, `/roles`, `/sessions`). Data services run
`DISABLE_AUTH=true` and trust the private docker network. This is a
deliberate, documented tradeoff: it removes a whole class of inter-service
auth failures at the cost of requiring the docker network to be a trust
boundary. It is appropriate because **no data-service port except the
frontend is exposed outside the host**.

## SC4 — RBAC that the UI and API agree on

Three roles (admin, analyst, viewer) with per-resource permissions
(`intelligence:read`, `iocs:write`, etc.) must be enforced server-side and
*reflected* client-side (hide buttons a viewer can't use) without the
client being the authority.

**Response:** the server is the authority — `tip_auth.require_permission`
guards every protected endpoint. The client mirrors the same logic in
`frontend/src/lib/store.ts` (`hasPermission`, `isAdmin`) purely to hide
chrome. Permission strings are seeded by `services/auth/app/seed.py` and
reconciled on every boot. A subtle bug class here — singular vs plural
permission names (`threat:write` vs `threats:write`) — was found and fixed
(commit `14d0489`); the canonical names are now audited from the actual
`require_permission` call sites.

## SC5 — Outbound egress control

A bank must know exactly what leaves its perimeter. Fifteen services each
making arbitrary outbound calls is an audit nightmare.

**Response:** outbound HTTP is constrained to (a) the per-source
ingesters calling their named feeds, and (b) the LiteLLM proxy calling the
configured AI provider. The proxy is the **single AI egress boundary** —
the bank can point it at an on-prem model or a specific cloud provider and
prove no other path exists. The compose file is the egress inventory.

## SC6 — SSRF in the investigation / dorking paths

`indicator-intel` fetches user-supplied indicators (IP/domain) from
multiple sources, and the dorking sub-service issues searches. A malicious
input could attempt to make the service fetch internal resources.

**Response:** investigations use a fixed set of external sources
(ip-api, Shodan, crt.sh, etc.) with the indicator passed as a *query
parameter*, not a fetch target — the service never fetches the
user-supplied URL directly. Dorking issues queries to Google CSE /
DuckDuckGo, not to the target. The attack surface is analysed in
`08_security/attack_surface_analysis.md`.

## SC7 — AI prompt-injection and data exfiltration

The AI layer reads threat data (including attacker-controlled content like
article text and IOC context). A crafted payload could attempt prompt
injection.

**Response:** the AI layer reads **processed data only**, never raw
user input on the ingest path. Outputs are constrained to typed Pydantic
schemas (`generate_structured`) with JSON-mode + validation + one retry.
The blast radius of a successful injection is one insight payload, which
an analyst reviews before acting (IOCs are *not* auto-promoted to the
firewall — the analyst is the gate).

## SC8 — Container and supply-chain security

Fifteen images, each with a dependency tree.

**Response:** every service pins its dependencies in `pyproject.toml`;
images are built from official slim Python bases; the AI gateway isolates
services from upstream-provider SDK churn. Detailed in
`08_security/container_security.md` and
`08_security/dependency_security.md`.

## Security posture summary

| Challenge | Primary control | Residual risk |
|---|---|---|
| Credential sprawl | Fernet vault + access log | `FERNET_KEY` compromise = full vault |
| Bootstrap | scoped bootstrap token | token leak on trusted network |
| Auth boundary | edge auth + trusted docker net | host compromise = data-service access |
| RBAC | server-side `require_permission` | misconfigured permission strings (mitigated by audit) |
| Egress | single AI proxy + named sources | operator misconfigures proxy target |
| SSRF | query-param not fetch-target | new source added without review |
| Prompt injection | processed-data-only + analyst gate | analyst acts on a poisoned insight |
| Supply chain | pinned deps + slim bases | unpatched CVE in a pinned dep |

The full risk register with likelihood × impact scoring is in
`08_security/risk_analysis.md`.
