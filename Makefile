.PHONY: help install dev demo seed test sandbox-image db-up db-down db-upgrade db-downgrade verify-llm export-users

.DEFAULT_GOAL := help

API_DIR := apps/api
API_VENV := $(CURDIR)/$(API_DIR)/.venv

ifeq ($(OS),Windows_NT)
API_PY := $(API_VENV)/Scripts/python.exe
else
API_PY := $(API_VENV)/bin/python
endif

help: ## Show this list of commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install API (Python venv) and dashboard (pnpm) dependencies
	python -m venv $(API_VENV)
	$(API_PY) -m pip install -e "$(API_DIR)[dev]"
	pnpm install

# Starts the docker-compose Postgres service and blocks until its
# healthcheck passes, so callers (db-upgrade, seed, dev) never race a
# still-starting container.
db-up: ## Start Postgres (docker compose) and wait for it to be healthy
	docker compose up -d postgres
	@echo "Waiting for postgres to become healthy..."
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' $$(docker compose ps -q postgres))" = "healthy" ]; do sleep 1; done
	@echo "postgres is healthy."

db-down: ## Stop Postgres
	docker compose down

db-upgrade: ## Run Alembic migrations to head
	cd $(API_DIR) && $(API_PY) -m alembic upgrade head

db-downgrade: ## Roll back one Alembic migration
	cd $(API_DIR) && $(API_PY) -m alembic downgrade -1

seed: db-up db-upgrade ## Reset the DB and found the demo company "Acme AI"
	$(API_PY) scripts/seed.py

dev: db-up db-upgrade ## Run the API (:8000) and dashboard (:3000) together
	@trap 'kill 0' EXIT INT TERM; \
	(cd $(API_DIR) && $(API_PY) -m uvicorn app.main:app --reload --port 8000) & \
	pnpm --filter @commander/dashboard dev & \
	wait

demo: seed dev ## One-command happy path: seed the demo company, then run the app

test: ## Run the backend test suite + dashboard typecheck + dashboard build
	cd $(API_DIR) && $(API_PY) -m pytest
	pnpm --filter @commander/dashboard typecheck
	pnpm --filter @commander/dashboard build

sandbox-image: ## Build the Docker image used by the execution sandbox (optional)
	docker build -t commander-sandbox -f sandbox/Dockerfile sandbox

verify-llm: ## Run one real Mission against a live Anthropic key + throwaway DB
	$(API_PY) scripts/verify_real_llm.py

export-users: ## Export all CEO accounts to CSV (no plaintext passwords) on stdout
	$(API_PY) scripts/export_users.py
