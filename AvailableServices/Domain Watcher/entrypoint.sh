#!/bin/sh
set -e

# Seed an initial admin user on first run if env vars are provided.
# If the user already exists, create_user.py prints a message and exits 0 — safe to re-run.
if [ -n "$ADMIN_USERNAME" ] && [ -n "$ADMIN_PASSWORD" ]; then
    echo "[entrypoint] Creating user '${ADMIN_USERNAME}' (skipped if already exists)..."
    python scripts/create_user.py -u "$ADMIN_USERNAME" -p "$ADMIN_PASSWORD" || true
fi

exec uvicorn main:app --host 0.0.0.0 --port 8080
