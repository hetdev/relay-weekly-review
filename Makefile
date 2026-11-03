# Relay — Weekly Activity Review. Local development entry points.
# Everything runs against a dedicated, disposable local PostgreSQL cluster.

PYTHON  := backend/.venv/bin/python
PIP     := backend/.venv/bin/pip
PSQL    := /opt/homebrew/opt/postgresql@17/bin/psql
PGCTL   := /opt/homebrew/opt/postgresql@17/bin/pg_ctl
PGBIN   := /opt/homebrew/opt/postgresql@17/bin
PGPORT  := 5433

ADMIN_URL := postgresql+psycopg://relay_admin@127.0.0.1:$(PGPORT)/relay_dev

.DEFAULT_GOAL := help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*## "}{printf "  %-16s %s\n", $$1, $$2}'

## Setup ------------------------------------------------------------------

db-init: ## One-time: init the local cluster, roles, and databases
	$(PGBIN)/initdb -D var/pgdata -E UTF8 --locale=C -A trust -U relay_admin
	$(MAKE) db-up
	$(PSQL) -h 127.0.0.1 -p $(PGPORT) -U relay_admin -d postgres -c "CREATE ROLE relay_app LOGIN"
	for db in relay_dev relay_test relay_recon; do $(PSQL) -h 127.0.0.1 -p $(PGPORT) -U relay_admin -d postgres -c "CREATE DATABASE $$db OWNER relay_admin" || exit $$?; done
	$(PSQL) -h 127.0.0.1 -p $(PGPORT) -U relay_admin -d postgres -c "GRANT CONNECT ON DATABASE relay_dev, relay_test, relay_recon TO relay_app"

db-up: ## Start the local PostgreSQL cluster (port 5433, loopback only)
	@if $(PGCTL) -D var/pgdata status >/dev/null 2>&1; then \
		echo "PostgreSQL is already running"; \
	else \
		$(PGCTL) -D var/pgdata -o "-p $(PGPORT) -k $(CURDIR)/var -c listen_addresses=127.0.0.1" -l var/pg.log start; \
	fi

db-down: ## Stop the local PostgreSQL cluster
	$(PGCTL) -D var/pgdata stop || true

venv: ## Create the backend virtualenv with pinned dependencies
	/opt/homebrew/bin/python3.12 -m venv backend/.venv
	$(PIP) install -q -r backend/requirements.txt

setup: venv db-up migrate seed grants frontend-install ## Full local setup (after `make db-init`)

## Database ---------------------------------------------------------------

migrate: ## Apply Alembic migrations to relay_dev (admin role)
	cd backend && RELAY_MIGRATION_DATABASE_URL="$(ADMIN_URL)" .venv/bin/alembic upgrade head

grants: ## Grant the read-only role SELECT on relay_dev
	$(PSQL) -h 127.0.0.1 -p $(PGPORT) -U relay_admin -d relay_dev -f scripts/sql/grants.sql

seed: ## Import the reviewed seed fixture (idempotent, verified by sha256)
	cd backend && .venv/bin/python -m app.reviews.seed --seed-file ../review-input/starter/seed.sql

seed-reset: ## Explicit reset + reimport of the disposable demo database
	cd backend && RELAY_ALLOW_RESET=1 .venv/bin/python -m app.reviews.seed --seed-file ../review-input/starter/seed.sql --reset

## Development ------------------------------------------------------------

backend-dev: ## Run the API on 127.0.0.1:8000 (read-only role)
	cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

frontend-install: ## Install frontend dependencies
	cd frontend && npm ci --ignore-scripts

frontend-dev: ## Run the UI on localhost:5173 (proxies /api to :8000)
	cd frontend && npm run dev

## Verification -----------------------------------------------------------

backend-test: ## Run the backend test suite (needs a running cluster)
	cd backend && .venv/bin/python -m pytest

backend-unit-test: ## Run policy/calendar tests without a database
	cd backend && .venv/bin/python -m pytest -m unit

bootstrap-test: ## Verify database initialization/startup in a disposable cluster
	$(PYTHON) scripts/test_bootstrap.py

frontend-test: ## Run the frontend test suite
	cd frontend && npm test

frontend-build: ## Type-check and build the frontend
	cd frontend && npm run build

test: backend-test frontend-test frontend-build ## Everything

sync-openapi: ## Regenerate frontend/src/features/review/openapi.json (API must be running)
	cd frontend && npm run sync-openapi

.PHONY: help db-init db-up db-down venv setup migrate grants seed seed-reset backend-dev frontend-install frontend-dev backend-test backend-unit-test bootstrap-test frontend-test frontend-build test sync-openapi
