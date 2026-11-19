#!/bin/sh
set -eu

exec uvicorn user_service.asgi:application --host 0.0.0.0 --port 8000 --workers 3 \
    --root-path "$(python -c 'from user_service.settings import FORCE_SCRIPT_NAME; print(FORCE_SCRIPT_NAME or "")')"
