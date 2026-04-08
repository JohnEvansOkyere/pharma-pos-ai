#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_SCRIPT="$ROOT_DIR/scripts/backup_postgres.sh"
CRON_SCHEDULE="${BACKUP_CRON_SCHEDULE:-0 20 * * *}"
CRON_TAG="# pharma-pos-ai backup schedule"
CRON_COMMAND="cd \"$ROOT_DIR\" && bash \"$BACKUP_SCRIPT\" >> \"$ROOT_DIR/backups/backup.log\" 2>&1"
CRON_ENTRY="$CRON_SCHEDULE $CRON_COMMAND $CRON_TAG"

mkdir -p "$ROOT_DIR/backups"

CURRENT_CRONTAB="$(mktemp)"
UPDATED_CRONTAB="$(mktemp)"
trap 'rm -f "$CURRENT_CRONTAB" "$UPDATED_CRONTAB"' EXIT

crontab -l > "$CURRENT_CRONTAB" 2>/dev/null || true
grep -vF "$CRON_TAG" "$CURRENT_CRONTAB" > "$UPDATED_CRONTAB" || true
printf '%s\n' "$CRON_ENTRY" >> "$UPDATED_CRONTAB"
crontab "$UPDATED_CRONTAB"

echo "Installed backup cron schedule:"
echo "$CRON_ENTRY"
echo "Backups will be written to: $ROOT_DIR/backups"
