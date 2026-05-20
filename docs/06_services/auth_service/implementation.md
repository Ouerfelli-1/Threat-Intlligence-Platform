# auth — Implementation Notes

## Files and their concrete responsibilities

| File | Lines of responsibility |
|---|---|
| `app/main.py` | startup hook: env guard, `init_engine`, bootstrap-fetch RS256 keys, build token resolver, `seed(session, resolver)`; mounts routers `auth, jwks, roles, sessions, users` |
| `app/security.py` | `init_keys`, RS256 `sign_token`/`decode_token`, argon2 `hash_password`/`verify_password`, `hash_token` (SHA-256) |
| `app/deps.py` | `_get_token_payload` (honours `DISABLE_AUTH` dev short-circuit), `require_admin`, `get_current_user_payload` |
| `app/seed.py` | `_ROLES`, `_SERVICE_ACCOUNTS`, idempotent reconcile, admin user creation |
| `app/routes/auth.py` | `/login`, `/refresh`, `/logout`, `/me` |
| `app/routes/users.py` | user CRUD + session revoke on change |
| `app/routes/roles.py` | role CRUD |
| `app/routes/sessions.py` | session list/revoke |
| `app/routes/jwks.py` | `/.well-known/jwks.json` |
| `app/models.py` | `Role`, `User`, `ServiceAccount`, `Session`, `AuditLog` |

## The dev-mode short-circuit

`app/deps.py` `_get_token_payload` returns a synthetic dev-admin payload
when `settings.disable_auth` is true:

```python
if settings.disable_auth:
    return {"kind": "user", "role": "admin", "perms": ["*"],
            "sub": "user:000...000", "username": "dev"}
```

In the deployed configuration auth itself runs with `DISABLE_AUTH=false`
(hardcoded in compose), so this branch is *not* taken for auth — it
remains a development convenience and a guard for local runs.

## Idempotent seed — implementation detail

`seed.py` reconciles permissions on every boot rather than only on first
insert. For roles:

```python
new_perms = list(role_def["permissions"])
if sorted(role.permissions or []) != sorted(new_perms):
    role.permissions = new_perms
```

For service accounts, `supplementary_permissions` are reconciled the same
way, and `bootstrap_token_hash` is (re)written from the resolver-fetched
token. This is why a permission fix in code (e.g. the scheduler grant in
`14d0489`) applies on restart with no manual SQL.

## Service-account token hashing

When `seed` runs with a non-null `token_resolver`, for each service
account it fetches `SVC_<NAME>_BOOTSTRAP_TOKEN` from the vault and stores
`hash_token(token)` in `bootstrap_token_hash`. `/service-login` (legacy)
validates a presented token by comparing hashes — the clear token is never
stored.

## Production guard

The first line of `_startup`:

```python
if settings.tip_env == "production" and settings.disable_auth:
    raise RuntimeError("DISABLE_AUTH cannot be true in production")
```

This is a deliberate fail-fast: a production deployment that accidentally
disabled auth refuses to start rather than silently serving an open API.

## What is intentionally simple

auth is a small, focused service. It has no AI, no Redis, no external
sources, no background jobs. This minimalism is by design — the
authentication authority should be the easiest service to audit and the
least likely to fail. Its entire surface is five route modules and two
logic modules.

## Testing hooks

- The dev short-circuit allows local frontend development without a live
  auth round-trip.
- The reconcile-on-boot seed means a test environment converges to the
  same role/permission state as production on startup.
- Session revocation is independently testable: revoke a session row,
  call `/me`, expect 401.
