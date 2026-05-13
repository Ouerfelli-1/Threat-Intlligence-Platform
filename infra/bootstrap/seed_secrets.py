"""Seed the secrets service database from prompt/credentials.env.

Usage:
    python infra/bootstrap/seed_secrets.py

Requirements:
    - FERNET_KEY in os.environ (or .env)
    - SECRETS_BOOTSTRAP_TOKEN in os.environ
    - Postgres reachable via DATABASE_URL (defaults to psycopg sync URL on localhost:5432)

What it does:
    1. Reads `prompt/credentials.env` line-by-line, ignoring comments and blank lines.
    2. Generates an RS256 keypair for the auth service (AUTH_RS256_PRIVATE_KEY / AUTH_RS256_PUBLIC_KEY).
    3. Generates per-service bootstrap tokens (SVC_<NAME>_BOOTSTRAP_TOKEN).
    4. Upserts every secret into the `secrets.secrets` table with Fernet-encrypted values.
"""

import os
import secrets as pysecrets
import sys
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import psycopg

ROOT = Path(__file__).resolve().parents[2]
CREDENTIALS_FILE = ROOT / "prompt" / "credentials.env"

SERVICE_NAMES = [
    # auth itself uses SECRETS_BOOTSTRAP_TOKEN, not SVC_AUTH_BOOTSTRAP_TOKEN
    "news-collector",
    "vuln-intel",
    "threat-intel",
    "ioc-collector",
    "threat-actors",
    "integrations",
    "cmdb",
    "flowviz",
    "asm",
    "domainwatch",
    "scheduler",
    "indicator-intel",
    "orchestrator",
]


def _read_credentials() -> dict[str, str]:
    if not CREDENTIALS_FILE.exists():
        print(f"[seed_secrets] {CREDENTIALS_FILE} not found, continuing with empty set")
        return {}
    out: dict[str, str] = {}
    for line in CREDENTIALS_FILE.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        key, _, value = s.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value:
            out[key] = value
    return out


def _generate_rsa_keypair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    pub_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    return priv_pem, pub_pem


def _build_secret_payload(creds: dict[str, str]) -> dict[str, str]:
    payload: dict[str, str] = dict(creds)
    priv, pub = _generate_rsa_keypair()
    payload["AUTH_RS256_PRIVATE_KEY"] = priv
    payload["AUTH_RS256_PUBLIC_KEY"] = pub
    for svc in SERVICE_NAMES:
        key = f"SVC_{svc.upper().replace('-', '_')}_BOOTSTRAP_TOKEN"
        if key not in payload:
            payload[key] = pysecrets.token_urlsafe(32)
    return payload


def _connect() -> psycopg.Connection:
    url = os.environ.get(
        "DATABASE_URL_SYNC",
        f"postgresql://tip:{os.environ.get('POSTGRES_PASSWORD', 'tip')}@localhost:5432/tip",
    )
    return psycopg.connect(url, autocommit=False)


def _ensure_schema_and_table(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS secrets")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS secrets.secrets (
                name text PRIMARY KEY,
                value_encrypted bytea NOT NULL,
                version int NOT NULL DEFAULT 1,
                metadata jsonb NOT NULL DEFAULT '{}',
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
    conn.commit()


def _upsert(conn: psycopg.Connection, fernet: Fernet, name: str, value: str) -> None:
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
            """,
            (name, encrypted, now, now),
        )


def main() -> int:
    fernet_key = os.environ.get("FERNET_KEY")
    if not fernet_key:
        print("FERNET_KEY missing — set it in .env or environment", file=sys.stderr)
        return 2
    fernet = Fernet(fernet_key.encode("utf-8"))

    creds = _read_credentials()
    payload = _build_secret_payload(creds)
    print(f"[seed_secrets] seeding {len(payload)} secrets")

    with _connect() as conn:
        _ensure_schema_and_table(conn)
        for name, value in payload.items():
            _upsert(conn, fernet, name, value)
        conn.commit()

    print("[seed_secrets] done. service bootstrap tokens are stored as SVC_<NAME>_BOOTSTRAP_TOKEN.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
