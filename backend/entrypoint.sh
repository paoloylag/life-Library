#!/bin/sh
set -eu

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  alembic upgrade head
fi
if [ "${APP_ENV:-local}" != "production" ]; then
  python -m app.seed_data
fi

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
