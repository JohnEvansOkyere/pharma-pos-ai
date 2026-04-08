#!/bin/bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: scripts/restore_postgres.sh <backup_file.dump>"
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/backend/.env"
BACKUP_FILE="$1"

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-pharma_pos}"
POSTGRES_USER="${POSTGRES_USER:-pharma_user}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE"
  exit 1
fi

echo "WARNING: This will overwrite data in database '$POSTGRES_DB'."
read -r -p "Type RESTORE to continue: " CONFIRM
if [ "$CONFIRM" != "RESTORE" ]; then
  echo "Restore cancelled."
  exit 1
fi

export PGPASSWORD="$POSTGRES_PASSWORD"
pg_restore \
  -h "$POSTGRES_HOST" \
  -p "$POSTGRES_PORT" \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  "$BACKUP_FILE"
unset PGPASSWORD

echo "Restore completed."
