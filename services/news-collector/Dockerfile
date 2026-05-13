FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt-dev gcc \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY packages/ /app/packages/
COPY services/news-collector/pyproject.toml /app/service/pyproject.toml
COPY services/news-collector/app/ /app/service/app/
COPY services/news-collector/alembic/ /app/service/alembic/
COPY services/news-collector/alembic.ini /app/service/alembic.ini

WORKDIR /app/service
RUN uv pip install --system --no-cache-dir -e .

ENV PYTHONPATH=/app/service
EXPOSE 8001
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
