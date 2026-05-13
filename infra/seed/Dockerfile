FROM python:3.11-slim

RUN pip install --no-cache-dir httpx

COPY infra/bootstrap/seed_knowledge_base.py /app/seed_knowledge_base.py
COPY prompt/companyprofile.json /seed/companyprofile.json

WORKDIR /app
CMD ["python", "/app/seed_knowledge_base.py"]
