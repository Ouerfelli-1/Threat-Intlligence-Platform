FROM python:3.11-slim

# Install Playwright system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --no-cache-dir uv
COPY packages/ /app/packages/
COPY services/domainwatch/pyproject.toml /app/service/pyproject.toml
COPY services/domainwatch/app/ /app/service/app/
COPY services/domainwatch/alembic/ /app/service/alembic/
COPY services/domainwatch/alembic.ini /app/service/alembic.ini
WORKDIR /app/service
RUN uv pip install --system --no-cache-dir -e .
RUN playwright install --with-deps chromium
ENV PYTHONPATH=/app/service
EXPOSE 8010
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
