#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON:-python}"
PORT="${PORT:-8000}"
REDIS_PORT="${REDIS_PORT:-6379}"

export DB_NAME="${DB_NAME:-ts_plugin}"
export DB_USER="${DB_USER:-postgres}"
export DB_PASSWORD="${DB_PASSWORD:-1234}"
export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT="${DB_PORT:-5432}"
export CELERY_BROKER_URL="${CELERY_BROKER_URL:-redis://localhost:${REDIS_PORT}/0}"
export CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND:-redis://localhost:${REDIS_PORT}/0}"

pids=()

cleanup() {
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing command: $1" >&2
    exit 1
  }
}

wait_for_postgres() {
  if command -v pg_isready >/dev/null 2>&1; then
    until PGPASSWORD="$DB_PASSWORD" pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; do
      echo "Waiting for Postgres at ${DB_HOST}:${DB_PORT}/${DB_NAME}..."
      sleep 1
    done
  fi

  if command -v psql >/dev/null 2>&1; then
    if ! output="$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "select 1;" 2>&1 >/dev/null)"; then
      echo "Cannot connect to Postgres at ${DB_HOST}:${DB_PORT}/${DB_NAME} as ${DB_USER}." >&2
      echo "$output" >&2
      exit 1
    fi

    version="$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc "show server_version_num;")"
    if [ "$version" -lt 140000 ]; then
      echo "PostgreSQL 14 or later is required; found $(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc "show server_version;")." >&2
      exit 1
    fi
  fi
}

start_redis() {
  if command -v redis-cli >/dev/null 2>&1 && redis-cli -p "$REDIS_PORT" ping >/dev/null 2>&1; then
    return
  fi

  require_cmd redis-server
  redis-server --port "$REDIS_PORT" --save "" --appendonly no &
  pids+=("$!")

  require_cmd redis-cli
  until redis-cli -p "$REDIS_PORT" ping >/dev/null 2>&1; do
    echo "Waiting for Redis on port ${REDIS_PORT}..."
    sleep 1
  done
}

require_cmd "$PYTHON"
wait_for_postgres
start_redis

"$PYTHON" manage.py migrate

"$PYTHON" -m uvicorn user_service.asgi:application --host 0.0.0.0 --port "$PORT" &
pids+=("$!")

"$PYTHON" -m celery -A user_service worker --loglevel=error --concurrency="${CELERY_CONCURRENCY:-20}" &
pids+=("$!")

echo "Django is running at http://localhost:${PORT}"
echo "Press Ctrl+C to stop local services."
wait
