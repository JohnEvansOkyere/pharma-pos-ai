#!/bin/bash
# Database initialization script

echo "🔧 Initializing database..."

# Navigate to backend directory
cd backend || exit

# Create migrations
echo "Creating initial migration..."
alembic revision --autogenerate -m "Initial migration"

# Run migrations
echo "Running migrations..."
alembic upgrade head

echo "✅ Database initialized!"

# Run seed script
cd ..
echo "🌱 Seeding database..."
python scripts/seed_data.py

echo "✅ All done!"
