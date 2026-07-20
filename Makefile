API_HOST ?= 127.0.0.1
API_PORT ?= 8000
WEB_HOST ?= 127.0.0.1
WEB_PORT ?= 3000
NEXT_PUBLIC_ASTRO_ABM_API_BASE_URL ?= http://$(API_HOST):$(API_PORT)
export NEXT_PUBLIC_ASTRO_ABM_API_BASE_URL

.PHONY: help status bootstrap up db-up down migrate maintain-now astro-daily research-store research-prepare product-snapshots fetch-local-data smoke checkpoint checkpoint-check check-api-port check-web-port api web product-smoke scenario-demo cleanup-guests open-source-audit test

help:
	@echo "Astro ABM one-command operations"
	@echo ""
	@echo "  make status           Check git, Docker, QuestDB, local data, and research snapshots"
	@echo "  make bootstrap        Create .env if missing, start QuestDB+maintenance, apply schemas"
	@echo "  make up               Start QuestDB plus maintenance daemon"
	@echo "  make db-up            Start QuestDB only"
	@echo "  make down             Stop Docker services without deleting volumes"
	@echo "  make migrate          Apply hourly and daily QuestDB schemas"
	@echo "  make maintain-now     Run one local hourly+daily maintenance pass"
	@echo "  make astro-daily      Ensure 100-year core daily astro data exists"
	@echo "  make research-store   Build ignored DuckDB full-history research store"
	@echo "  make research-prepare Run selectable public/local/formal research preparation"
	@echo "  make product-snapshots Refresh Scenario/Workbench daily product snapshots"
	@echo "  make fetch-local-data Fetch ignored SPX/Gold/DXY/Credit local research CSVs"
	@echo "  make smoke            Run small public smoke build"
	@echo "  make checkpoint       Regenerate research workflow checkpoint"
	@echo "  make checkpoint-check Validate existing checkpoint outputs only"
	@echo "  make api              Run the local Astro ABM product API on API_HOST:API_PORT"
	@echo "  make web              Run the local Astro ABM product web UI on WEB_HOST:WEB_PORT"
	@echo "  make product-smoke    Run API tests and create a mock demo scenario"
	@echo "  make scenario-demo    Create one deterministic local scenario report"
	@echo "  make cleanup-guests   Remove expired anonymous workspaces and their reports"
	@echo "  make open-source-audit Check license, Git tracking, ignore rules, and secret patterns"
	@echo "  make test             Run the full test suite"

status:
	uv run python scripts/astro_abm_ops.py status

bootstrap:
	uv run python scripts/astro_abm_ops.py bootstrap

up:
	uv run python scripts/astro_abm_ops.py up

db-up:
	uv run python scripts/astro_abm_ops.py up --db-only

down:
	uv run python scripts/astro_abm_ops.py down

migrate:
	uv run python scripts/astro_abm_ops.py migrate

maintain-now:
	uv run python scripts/astro_abm_ops.py maintain-now --allow-partial

astro-daily:
	uv run python scripts/astro_abm_ops.py astro-daily

research-store:
	uv run python scripts/astro_abm_ops.py research-store

research-prepare:
	uv run python scripts/astro_abm_ops.py research-prepare

product-snapshots:
	uv run python scripts/astro_abm_ops.py product-snapshots

fetch-local-data:
	uv run python scripts/astro_abm_ops.py fetch-local-data --all --accept-research-local-terms

smoke:
	uv run python scripts/astro_abm_ops.py smoke

checkpoint:
	uv run python scripts/astro_abm_ops.py checkpoint

checkpoint-check:
	uv run python scripts/astro_abm_ops.py checkpoint --check-only

check-api-port:
	uv run python scripts/check_local_port.py --host $(API_HOST) --port $(API_PORT) --service "Astro ABM API" --retry-command "make api API_PORT=18000"

check-web-port:
	uv run python scripts/check_local_port.py --host $(WEB_HOST) --port $(WEB_PORT) --service "Astro ABM Web" --retry-command "make web WEB_PORT=13000 API_PORT=$(API_PORT)"

api: check-api-port
	uv run uvicorn astro_abm_api.main:app --app-dir apps/api --host $(API_HOST) --port $(API_PORT) --reload --reload-dir apps/api

web: check-web-port
	cd apps/web && npm run dev -- --hostname $(WEB_HOST) --port $(WEB_PORT)

product-smoke:
	uv run --extra dev pytest apps/api/tests
	$(MAKE) scenario-demo

scenario-demo:
	uv run python scripts/create_demo_scenario.py

cleanup-guests:
	uv run python scripts/cleanup_guest_worldlines.py

open-source-audit:
	uv run python scripts/audit_open_source_readiness.py --history

test:
	uv run --extra dev pytest
