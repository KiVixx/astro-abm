.PHONY: help status bootstrap up db-up down migrate maintain-now astro-daily smoke checkpoint checkpoint-check test

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
	@echo "  make smoke            Run small public smoke build"
	@echo "  make checkpoint       Regenerate research workflow checkpoint"
	@echo "  make checkpoint-check Validate existing checkpoint outputs only"
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

smoke:
	uv run python scripts/astro_abm_ops.py smoke

checkpoint:
	uv run python scripts/astro_abm_ops.py checkpoint

checkpoint-check:
	uv run python scripts/astro_abm_ops.py checkpoint --check-only

test:
	uv run --extra dev pytest
