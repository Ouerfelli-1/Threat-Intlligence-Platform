# auth — Request Flows

## Login

```mermaid
sequenceDiagram
    autonumber
    participant C as Client (BFF)
    participant R as routes/auth.py /login
    participant S as security.py
    participant DB as Postgres auth

    C->>R: POST /login {username, password}
    R->>DB: SELECT user WHERE username
    alt user missing or inactive
        R-->>C: 401
    else found
        R->>S: verify_password(hash, password)  [argon2]
        alt mismatch
            R-->>C: 401
        else match
            R->>S: sign access JWT (1h) + refresh token
            R->>DB: INSERT session (refresh_token_hash, exp, UA, IP)
            R->>DB: INSERT audit_log (login)
            R-->>C: 200 {access_token, refresh_token}
        end
    end
```

## /me with revocation check

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant R as routes/auth.py /me
    participant D as deps.py
    participant DB as Postgres auth

    C->>R: GET /me (Bearer)
    R->>D: decode + validate JWT (RS256)
    alt invalid/expired
        D-->>C: 401
    else valid
        D->>DB: SELECT session WHERE id = jwt.sid
        alt session revoked or missing
            DB-->>R: revoked
            R-->>C: 401
        else active
            R->>DB: SELECT user + role permissions
            R-->>C: 200 {id, username, role, permissions}
        end
    end
```

## Admin demotes a user (cascade revoke)

```mermaid
sequenceDiagram
    autonumber
    participant A as Admin (BFF)
    participant R as routes/users.py PATCH
    participant DB as Postgres auth
    participant V as Victim's next /me poll

    A->>R: PATCH /users/{id} {role_id: analyst}
    R->>DB: UPDATE user role
    R->>DB: UPDATE sessions SET revoked=true WHERE user_id
    R-->>A: 200
    Note over V: within 15s
    V->>R: GET /me (old token)
    R->>DB: session revoked
    R-->>V: 401 -> frontend clears auth + redirects /login
```

This sequence is the concrete answer to the requirement "a revoked user
must be logged out without a manual refresh" — the 15-second `/me` poll in
`frontend/src/app/(app)/layout.tsx` closes the loop.

## Refresh

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant R as routes/auth.py /refresh
    participant DB as Postgres auth
    C->>R: POST /refresh {refresh_token}
    R->>DB: SELECT session WHERE refresh_token_hash = sha256(token)
    alt missing/expired/revoked
        R-->>C: 401
    else valid
        R->>R: sign new access JWT
        R-->>C: 200 {access_token}
    end
```
