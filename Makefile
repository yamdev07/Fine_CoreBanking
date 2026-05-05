.PHONY: help up down restart logs build rebuild test lint migrate reset \
        test-accounting test-reporting shell-accounting shell-reporting \
        db-shell redis-cli

COMPOSE        := docker compose
ACCOUNTING_SVC := accounting-service
REPORTING_SVC  := reporting-service
FRONTEND_SVC   := frontend

# ── Default target ───────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "Fine_CoreBanking — Available make targets"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  make up               Start the full stack (detached)"
	@echo "  make down             Stop and remove containers"
	@echo "  make restart          down + up"
	@echo "  make logs             Tail logs for all services"
	@echo "  make build            Build images (with cache)"
	@echo "  make rebuild          Build images (no cache, --pull)"
	@echo "  make migrate          Run Alembic migrations (upgrade head)"
	@echo "  make reset            Full dev reset (images + volumes + migrate)"
	@echo ""
	@echo "  make test             Run all tests (accounting + reporting)"
	@echo "  make test-accounting  Run accounting_service tests only"
	@echo "  make test-reporting   Run reporting_service tests only"
	@echo ""
	@echo "  make lint             Run ruff on both services"
	@echo ""
	@echo "  make shell-accounting  Open shell in accounting-service container"
	@echo "  make shell-reporting   Open shell in reporting-service container"
	@echo "  make db-shell          psql session (accounting DB)"
	@echo "  make redis-cli         redis-cli session"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""

# ── Stack lifecycle ──────────────────────────────────────────────────────────
up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down --remove-orphans

restart: down up

logs:
	$(COMPOSE) logs -f

# ── Build ────────────────────────────────────────────────────────────────────
build:
	$(COMPOSE) build

rebuild:
	$(COMPOSE) build --no-cache --pull

# ── Migrations ───────────────────────────────────────────────────────────────
migrate:
	$(COMPOSE) run --rm $(ACCOUNTING_SVC) alembic upgrade head

# ── Tests ────────────────────────────────────────────────────────────────────
test: test-accounting test-reporting

test-accounting:
	@echo "▶ Running accounting_service tests..."
	cd accounting_service && poetry run pytest tests/ -v --tb=short --cov=app --cov-report=term-missing

test-reporting:
	@echo "▶ Running reporting_service tests..."
	cd reporting_service && poetry run pytest tests/ -v --tb=short --cov=app --cov-report=term-missing

# ── Lint ─────────────────────────────────────────────────────────────────────
lint:
	@echo "▶ Linting accounting_service..."
	cd accounting_service && poetry run ruff check app/ tests/ && poetry run ruff format app/ tests/ --check
	@echo "▶ Linting reporting_service..."
	cd reporting_service && poetry run ruff check app/ tests/ && poetry run ruff format app/ tests/ --check

# ── Shell access ─────────────────────────────────────────────────────────────
shell-accounting:
	$(COMPOSE) exec $(ACCOUNTING_SVC) sh

shell-reporting:
	$(COMPOSE) exec $(REPORTING_SVC) sh

db-shell:
	$(COMPOSE) exec postgres psql -U postgres -d accounting_db

redis-cli:
	$(COMPOSE) exec redis-accounting redis-cli

# ── Full reset ───────────────────────────────────────────────────────────────
reset:
	@bash scripts/reset_dev.sh
