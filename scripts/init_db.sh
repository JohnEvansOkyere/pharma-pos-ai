#!/bin/bash
# Database initialization script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🔧 Initializing database..."

# Navigate to backend directory
cd "${REPO_ROOT}/backend" || exit

if [ -x "${REPO_ROOT}/backend/venv/bin/python" ]; then
    PYTHON_BIN="${REPO_ROOT}/backend/venv/bin/python"
else
    PYTHON_BIN="${PYTHON:-python}"
fi

# Run checked-in migrations
echo "Running migrations to head..."
"${PYTHON_BIN}" -m alembic upgrade head

echo "✅ Database initialized!"

cd "${REPO_ROOT}"

if [ "${SEED_DATABASE:-false}" = "true" ]; then
    echo "🌱 Seeding database..."
    "${PYTHON_BIN}" scripts/seed_data.py
else
    echo "ℹ️ Schema was migrated, but no sample data was inserted."
    echo "ℹ️ For development seed data, run: SEED_DATABASE=true bash scripts/init_db.sh"
fi

echo "✅ All done!"
