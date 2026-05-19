#!/usr/bin/env bash
set -euo pipefail

echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete. Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
