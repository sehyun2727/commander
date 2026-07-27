.PHONY: install dev seed test sandbox-image db-up db-down db-upgrade db-downgrade verify-llm

API_DIR := apps/api
API_VENV := $(CURDIR)/$(API_DIR)/.venv

ifeq ($(OS),Windows_NT)
API_PY := $(API_VENV)/Scripts/python.exe
else
API_PY := $(API_VENV)/bin/python
endif

install:
	python -m venv $(API_VENV)
	$(API_PY) -m pip install -e "$(API_DIR)[dev]"
	pnpm install

# Starts the docker-compose Postgres service and blocks until its
# healthcheck passes, so callers (db-upgrade, seed, dev) never race a
# still-starting container.
db-up:
	docker compose up -d postgres
	@echo "Waiting for postgres to become healthy..."
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' $$(docker compose ps -q postgres))" = "healthy" ]; do sleep 1; done
	@echo "postgres is healthy."

db-down:
	docker compose down

db-upgrade:
	cd $(API_DIR) && $(API_PY) -m alembic upgrade head

db-downgrade:
	cd $(API_DIR) && $(API_PY) -m alembic downgrade -1

seed: db-up db-upgrade
	$(API_PY) scripts/seed.py

dev: db-up db-upgrade
	@trap 'kill 0' EXIT INT TERM; \
	(cd $(API_DIR) && $(API_PY) -m uvicorn app.main:app --reload --port 8000) & \
	pnpm --filter @commander/dashboard dev & \
	wait

test:
	cd $(API_DIR) && $(API_PY) -m pytest
	pnpm --filter @commander/dashboard typecheck
	pnpm --filter @commander/dashboard build

sandbox-image:
	docker build -t commander-sandbox -f sandbox/Dockerfile sandbox

verify-llm:
	$(API_PY) scripts/verify_real_llm.py
