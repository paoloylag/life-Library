#!/bin/sh
set -eu

alembic upgrade head
if [ "${APP_ENV:-local}" != "production" ]; then
  python -m app.seed_data
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
