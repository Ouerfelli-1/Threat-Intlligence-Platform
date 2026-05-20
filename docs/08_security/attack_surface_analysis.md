# Attack Surface Analysis

## External attack surface (internet-facing)

The platform's external surface is intentionally minimal.

| Surface | Exposure | Notes |
|---|---|---|
| frontend `:3000` | **published** (the one required port) | behind a TLS reverse proxy in production |
| service ports `:8001–8014` | published for diagnostics | should be firewalled/removed in production |
| litellm `:4000` | published for diagnostics | should be firewalled in production |
| Postgres / Redis / PgBouncer | internal only | never published |

**Hardened production target:** only `:443` (reverse proxy → frontend
`:3000`) reachable from outside the host.

## Inbound request surface (per service)

Every service exposes a FastAPI app with:
- `/health` (open — for smoke tests).
- `/docs` + `/openapi.json` (FastAPI default — should be disabled or
  auth-gated in production).
- the service's routes (permission-guarded server-side).

The OpenAPI documents in `OpenAPI/` are the inventory of every route per
service.

## Outbound (egress) surface

The platform makes outbound calls only from:

| Service | Outbound destination |
|---|---|
| news-collector | configured RSS/Atom feeds |
| vuln-intel | NVD, FIRST.org EPSS, CISA KEV |
| threat-intel | supply-chain RSS, HIBP |
| ioc-collector | abuse.ch (ThreatFox/MalBazaar), OTX |
| threat-actors | MITRE STIX, ransomware.live |
| integrations | Wazuh, MISP |
| asm | crt.sh, Shodan, passive DNS sources |
| domainwatch | DNS, WHOIS, OTX, target sites (screenshot) |
| indicator-intel | ip-api, Shodan, crt.sh, Google CSE, DuckDuckGo |
| litellm | the configured AI provider |

This list **is** the egress allowlist the bank's firewall team needs. The
compose file plus this table is the complete egress inventory.

## The single AI egress boundary

All AI traffic funnels through the LiteLLM proxy. This is the security
keystone for the AI feature: the bank can point the proxy at an on-prem
model or a specific cloud provider and **prove** no other path to a model
exists, because no service holds a provider key — they hold only the proxy
master key.

## SSRF surface

The two paths that fetch based on user input:

- **indicator-intel investigation** — the target IP/domain is passed as a
  *query parameter* to fixed services (ip-api, Shodan, crt.sh), not used
  as a fetch URL. No SSRF.
- **dorking** — the target is embedded in a search *query* sent to Google
  CSE / DuckDuckGo, not fetched. No SSRF.
- **domainwatch** — fetches the monitored domain to screenshot it. This is
  the one place a user-named target is fetched; targets are operator-added
  domains (not arbitrary attacker input), bounding the risk.

## Authenticated surface reduction

Because data services run `DISABLE_AUTH=true`, their *authentication*
surface is zero — but they are only reachable from the trusted network.
The real authenticated surface is the auth service and the BFF edge. This
concentrates the auth attack surface into the smallest, most-audited
component (auth: 5 route modules, 2 logic modules).

## Frontend surface

- The BFF (`/api/[...path]`) proxies to a fixed `SERVICE_MAP` — an
  attacker cannot make the BFF call an arbitrary host; the first path
  segment must match a known service key.
- The SPA stores the token in `localStorage` (Zustand persist) — XSS would
  expose it; mitigated by React's default escaping and no `dangerouslySet
  InnerHTML` on untrusted content. Content-Security-Policy hardening is a
  documented future improvement.

## Surface change log

New surfaces added during the project, each reviewed:
- **dorking** (`/dorks/*`) — query-param only, no SSRF.
- **notifications** (`/notifications/*`, `/internal/notify`) — internal
  emit is unauthenticated on the trusted network (consistent with the
  edge-auth model); SMTP creds are vault-only.
