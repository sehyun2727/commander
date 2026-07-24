.PHONY: install dev seed test sandbox-image

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

seed:
	$(API_PY) scripts/seed.py

dev:
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
