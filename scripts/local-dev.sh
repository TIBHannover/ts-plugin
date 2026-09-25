#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON:-python}"
PORT="${PORT:-8000}"
REDIS_PORT="${REDIS_PORT:-6379}"

export DB_NAME="${DB_NAME:-ts_db}"
<<<<<<< HEAD
export DB_USER="${DB_USER:-ts}"
=======
export DB_USER="${DB_USER:-postgres}"
>>>>>>> main
export DB_PASSWORD="${DB_PASSWORD:-1234}"
export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT="${DB_PORT:-5432}"
export DEBUG_MODE="${DEBUG_MODE:-True}"
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

postgres_is_ready() {
  "$PYTHON" -c 'import os; os.environ.setdefault("DJANGO_SETTINGS_MODULE", "user_service.settings"); os.environ.setdefault("PGCONNECT_TIMEOUT", "1"); from django.db import connection; connection.ensure_connection(); connection.close()' >/dev/null 2>&1
}

wait_for_postgres() {
  until postgres_is_ready; do
    echo "Waiting for Postgres at ${DB_HOST}:${DB_PORT}/${DB_NAME}..."
    sleep 1
  done
}

redis_is_ready() {
  "$PYTHON" -c 'import os; from redis import Redis; Redis.from_url(os.environ["CELERY_BROKER_URL"], socket_connect_timeout=1, socket_timeout=1).ping()' >/dev/null 2>&1
}

start_redis() {
  if redis_is_ready; then
    return
  fi

  # require_cmd redis-server
  # redis-server --port "$REDIS_PORT" --save "" --appendonly no &
  # pids+=("$!")

<<<<<<< HEAD
  # require_cmd redis-cli
  # until redis-cli -p "$REDIS_PORT" ping >/dev/null 2>&1; do
  #   echo "Waiting for Redis on port ${REDIS_PORT}..."
  #   sleep 1
  # done
=======
  until redis_is_ready; do
    echo "Waiting for Redis on port ${REDIS_PORT}..."
    sleep 1
  done
>>>>>>> main
}

require_cmd "$PYTHON"
wait_for_postgres
start_redis

"$PYTHON" manage.py migrate

"$PYTHON" -m uvicorn user_service.asgi:application --host 0.0.0.0 --port "$PORT" &
pids+=("$!")

<<<<<<< HEAD
# "$PYTHON" -m celery -A user_service worker --loglevel=error --concurrency="${CELERY_CONCURRENCY:-20}" &
# pids+=("$!")
"$PYTHON" -m celery -A user_service worker --loglevel=error --pool=solo &
=======
"$PYTHON" -m celery -A user_service worker --loglevel=error --pool=solo --concurrency=1 &
>>>>>>> main
pids+=("$!")

echo "Django is running at http://localhost:${PORT}"
echo "Press Ctrl+C to stop local services."
wait
