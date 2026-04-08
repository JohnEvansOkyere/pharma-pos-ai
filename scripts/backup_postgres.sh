#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/backend/.env"
BACKUP_DIR="$ROOT_DIR/backups"

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
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
BACKUP_STATUS_FILE="$BACKUP_DIR/latest_backup.txt"

mkdir -p "$BACKUP_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/${POSTGRES_DB}_backup_${TIMESTAMP}.dump"

export PGPASSWORD="$POSTGRES_PASSWORD"
pg_dump \
  -h "$POSTGRES_HOST" \
  -p "$POSTGRES_PORT" \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  -F c \
  -f "$BACKUP_FILE"
unset PGPASSWORD

printf '%s\n' "$BACKUP_FILE" > "$BACKUP_STATUS_FILE"

find "$BACKUP_DIR" \
  -maxdepth 1 \
  -type f \
  -name "${POSTGRES_DB}_backup_*.dump" \
  -mtime +"$BACKUP_RETENTION_DAYS" \
  -delete

echo "Backup created: $BACKUP_FILE"
echo "Retention policy: keep ${BACKUP_RETENTION_DAYS} day(s) of backups"
