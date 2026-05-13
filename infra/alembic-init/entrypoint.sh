#!/usr/bin/env sh
set -eu

# Run all per-service Alembic migrations. Each service has its own alembic config under
# services/<name>/alembic.ini. Iteration order does not matter because schemas are isolated
# and no FKs cross schemas.

echo "[alembic-init] starting migrations against ${DATABASE_URL%@*}@..."

for svc_dir in /app/services/*/; do
  svc=$(basename "$svc_dir")
  cfg="$svc_dir/alembic.ini"
  if [ -f "$cfg" ]; then
    echo "[alembic-init] migrating $svc"
    (cd "$svc_dir" && alembic -c alembic.ini upgrade head) || {
      echo "[alembic-init] FAILED for $svc"; exit 1; }
  else
    echo "[alembic-init] skipping $svc (no alembic.ini)"
  fi
done

echo "[alembic-init] all migrations complete"
