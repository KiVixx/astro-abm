.PHONY: help status bootstrap up db-up down migrate maintain-now astro-daily research-store research-prepare fetch-local-data smoke checkpoint checkpoint-check api web product-smoke scenario-demo test

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
	@echo "  make fetch-local-data Fetch ignored SPX/Gold/DXY/Credit local research CSVs"
	@echo "  make smoke            Run small public smoke build"
	@echo "  make checkpoint       Regenerate research workflow checkpoint"
	@echo "  make checkpoint-check Validate existing checkpoint outputs only"
	@echo "  make api              Run the local Astro ABM product API"
	@echo "  make web              Run the local Astro ABM product web UI"
	@echo "  make product-smoke    Run API tests and create a mock demo scenario"
	@echo "  make scenario-demo    Create one deterministic local scenario report"
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

fetch-local-data:
	uv run python scripts/astro_abm_ops.py fetch-local-data --all --accept-research-local-terms

smoke:
	uv run python scripts/astro_abm_ops.py smoke

checkpoint:
	uv run python scripts/astro_abm_ops.py checkpoint

checkpoint-check:
	uv run python scripts/astro_abm_ops.py checkpoint --check-only

api:
	uv run uvicorn astro_abm_api.main:app --app-dir apps/api --reload

web:
	cd apps/web && npm run dev

product-smoke:
	uv run --extra dev pytest apps/api/tests
	$(MAKE) scenario-demo

scenario-demo:
	uv run python scripts/create_demo_scenario.py

test:
	uv run --extra dev pytest
