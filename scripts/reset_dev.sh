#!/usr/bin/env bash
# reset_dev.sh — Full development environment reset for Fine_CoreBanking
# Usage: ./scripts/reset_dev.sh [--keep-data]
#
# By default this script tears down all containers, volumes, and orphans,
# rebuilds images from scratch, then brings the stack back up and runs
# Alembic migrations.  Pass --keep-data to preserve the PostgreSQL volume.

set -euo pipefail

KEEP_DATA=false
for arg in "$@"; do
  case $arg in
    --keep-data) KEEP_DATA=true ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

COMPOSE_FILE="$(dirname "$0")/../docker-compose.yml"
cd "$(dirname "$0")/.."

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Fine_CoreBanking — Dev Environment Reset"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Stop and remove containers ───────────────────────────────────────────
echo ""
echo "▶ Stopping containers..."
docker compose -f "$COMPOSE_FILE" down --remove-orphans

if [ "$KEEP_DATA" = false ]; then
  echo "▶ Removing volumes (use --keep-data to preserve)..."
  docker compose -f "$COMPOSE_FILE" down -v
fi

# ── 2. Remove dangling images built by this project ──────────────────────────
echo ""
echo "▶ Removing project images..."
docker images --filter "dangling=true" -q | xargs -r docker rmi || true
docker rmi core-banking-accounting core-banking-reporting core-banking-frontend 2>/dev/null || true

# ── 3. Rebuild images ────────────────────────────────────────────────────────
echo ""
echo "▶ Building images (no cache)..."
docker compose -f "$COMPOSE_FILE" build --no-cache --pull

# ── 4. Start infrastructure (Postgres, Redis, Kafka) ─────────────────────────
echo ""
echo "▶ Starting infrastructure services..."
docker compose -f "$COMPOSE_FILE" up -d postgres redis zookeeper kafka
echo "   Waiting for Postgres to be ready..."
until docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U postgres -q; do
  sleep 1
done
echo "   Postgres is ready."

# ── 5. Run Alembic migrations ────────────────────────────────────────────────
echo ""
echo "▶ Running Alembic migrations (accounting_service)..."
docker compose -f "$COMPOSE_FILE" run --rm accounting-service \
  sh -c "alembic upgrade head"

# ── 6. Start remaining services ──────────────────────────────────────────────
echo ""
echo "▶ Starting all services..."
docker compose -f "$COMPOSE_FILE" up -d

# ── 7. Health check summary ──────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Services"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Frontend        → http://localhost:3000"
echo "  Accounting API  → http://localhost:8000/docs"
echo "  Reporting API   → http://localhost:8001/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✓ Reset complete."
