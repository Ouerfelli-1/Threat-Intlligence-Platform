"""Upsert one or more secrets into the vault directly (Fernet-encrypted).

Used for two cases the full seed script doesn't cleanly handle:
  1. First-time addition of a NEW secret name (e.g. LITELLM_MASTER_KEY) without
     re-running the full seed and re-rotating every per-service bootstrap token.
  2. Rotating a single value (e.g. GITHUB_API_KEY) without editing
     credentials.env.

Usage:
    FERNET_KEY=... python set_secrets.py KEY1=value1 KEY2=value2 ...

  Or read pairs from environment (one per line in the form NAME=value) via
  stdin:
    cat secrets.txt | FERNET_KEY=... python set_secrets.py -

Each value is Fernet-encrypted, upserted into secrets.secrets, and the row's
version is bumped on UPDATE so audit log + UI both reflect the change.

The script connects via $DATABASE_URL_SYNC (defaults to localhost:5432); when
run from the host shell where Postgres isn't exposed, invoke it inside an
ephemeral container attached to the platform's docker network.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import psycopg
from cryptography.fernet import Fernet


def _connect() -> psycopg.Connection:
    url = os.environ.get(
        "DATABASE_URL_SYNC",
        f"postgresql://tip:{os.environ.get('POSTGRES_PASSWORD', 'tip')}@localhost:5432/tip",
    )
    return psycopg.connect(url, autocommit=False)


def _upsert(conn: psycopg.Connection, fernet: Fernet, name: str, value: str) -> str:
    """Upsert a secret. Returns 'created' or 'updated:v<n>' for logging."""
    encrypted = fernet.encrypt(value.encode("utf-8"))
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO secrets.secrets (name, value_encrypted, version, metadata, created_at, updated_at)
            VALUES (%s, %s, 1, '{}', %s, %s)
            ON CONFLICT (name) DO UPDATE
            SET value_encrypted = EXCLUDED.value_encrypted,
                version = secrets.secrets.version + 1,
                updated_at = EXCLUDED.updated_at
            RETURNING version
            """,
            (name, encrypted, now, now),
        )
        version = cur.fetchone()[0]
    return "created" if version == 1 else f"updated:v{version}"


def _collect_pairs(argv: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for a in argv:
        if a == "-":
            for line in sys.stdin:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                pairs.append((k.strip(), v.strip()))
        elif "=" in a:
            k, _, v = a.partition("=")
            pairs.append((k.strip(), v.strip()))
        else:
            print(f"[set_secrets] ignoring arg {a!r} (no '=')", file=sys.stderr)
    return pairs


def main() -> int:
    fernet_key = os.environ.get("FERNET_KEY")
    if not fernet_key:
        print("FERNET_KEY missing in environment", file=sys.stderr)
        return 2
    fernet = Fernet(fernet_key.encode("utf-8"))

    pairs = _collect_pairs(sys.argv[1:])
    if not pairs:
        print("usage: set_secrets.py KEY=value [KEY2=value2 ...]   (or '-' for stdin)", file=sys.stderr)
        return 2

    with _connect() as conn:
        for name, value in pairs:
            outcome = _upsert(conn, fernet, name, value)
            # Log only the first 8 chars so we never leak the full secret.
            shown = value[:8] if len(value) >= 8 else value
            print(f"[set_secrets] {name:24s} -> {outcome}  (first8={shown!r}, len={len(value)})")
        conn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
