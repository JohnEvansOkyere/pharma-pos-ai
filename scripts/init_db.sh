#!/bin/bash
# Database initialization script

set -e

echo "🔧 Initializing database..."

# Navigate to backend directory
cd backend || exit

# Run checked-in migrations
echo "Running migrations to head..."
alembic upgrade head

echo "✅ Database initialized!"

cd ..

if [ "${SEED_DATABASE:-false}" = "true" ]; then
    echo "🌱 Seeding database..."
    python scripts/seed_data.py
else
    echo "ℹ️ Schema was migrated, but no sample data was inserted."
    echo "ℹ️ For development seed data, run: SEED_DATABASE=true bash scripts/init_db.sh"
fi

echo "✅ All done!"
