FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY packages/ /app/packages/
COPY services/ioc-collector/pyproject.toml /app/service/pyproject.toml
COPY services/ioc-collector/app/ /app/service/app/
COPY services/ioc-collector/alembic/ /app/service/alembic/
COPY services/ioc-collector/alembic.ini /app/service/alembic.ini
WORKDIR /app/service
RUN uv pip install --system --no-cache-dir -e .
ENV PYTHONPATH=/app/service
EXPOSE 8004
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
