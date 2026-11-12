#!/bin/sh
set -e
uv run alembic upgrade head
if [ "${SEED_ON_START:-true}" = "true" ]; then
  uv run python -m app.seed.run
fi
exec uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
