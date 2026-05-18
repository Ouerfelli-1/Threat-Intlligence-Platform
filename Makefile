.PHONY: seed migrate up down logs psql smoke-test build clean check-llm

COMPOSE = docker compose -f infra/docker-compose.yml --env-file .env

seed:
	python infra/bootstrap/seed_secrets.py

migrate:
	$(COMPOSE) run --rm alembic-init

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f $(svc)

psql:
	$(COMPOSE) exec postgres psql -U tip -d tip

smoke-test:
	python infra/bootstrap/smoke_test.py

# Bisect "AI chat doesn't work" — prints the first failing step in the
# secrets -> vault -> proxy -> upstream-provider chain.
check-llm:
	python infra/bootstrap/check_litellm.py

build:
	$(COMPOSE) build

clean:
	$(COMPOSE) down -v
