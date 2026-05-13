FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      libxml2-dev libxslt-dev gcc \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY packages/ /app/packages/
COPY services/ /app/services/
COPY infra/alembic-init/entrypoint.sh /app/entrypoint.sh
COPY infra/alembic-init/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

# Install shared packages so service env.py imports (`from tip_db import build_metadata`,
# `from tip_source_health import build_source_health_table`) resolve at migration time.
# Service `app` packages are NOT pip-installed — they would collide on the shared `app`
# namespace. The entrypoint cd's into each service dir, and each alembic.ini sets
# `prepend_sys_path = .`, which makes `from app.models import METADATA` resolve to the
# service's own on-disk `app/` directory.
RUN for d in /app/packages/*/; do \
      uv pip install --system --no-cache-dir -e "$d"; \
    done

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
