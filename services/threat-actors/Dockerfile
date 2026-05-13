FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY packages/ /app/packages/
COPY services/threat-actors/pyproject.toml /app/service/pyproject.toml
COPY services/threat-actors/app/ /app/service/app/
COPY services/threat-actors/alembic/ /app/service/alembic/
COPY services/threat-actors/alembic.ini /app/service/alembic.ini
WORKDIR /app/service
RUN uv pip install --system --no-cache-dir -e .
ENV PYTHONPATH=/app/service
EXPOSE 8005
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
