# Backup And Restore Guide

## Purpose

This guide explains how to back up and restore the local PostgreSQL database for Pharma POS AI.

This is for real client operation, not Docker-only development.

## Backup Strategy

Recommended minimum policy for a pharmacy:

- one automatic local backup every day
- one manual backup before major updates
- one weekly copy to external storage
- test restore before going live for any client

## Backup Location

The scripts store backups in:

- [backups](/home/grejoy/Projects/pharma-pos-ai/backups)

Backup format:

- PostgreSQL custom dump format: `.dump`

This is better than plain SQL for controlled restore operations.

## Windows Backup

Use:

- [backup.bat](/home/grejoy/Projects/pharma-pos-ai/backup.bat)

What it does:

- reads PostgreSQL settings from [backend/.env](/home/grejoy/Projects/pharma-pos-ai/backend/.env)
- creates `backups\pharma_pos_backup_YYYYMMDD_HHMMSS.dump`
- uses `pg_dump`
- writes `backups\latest_backup.txt`
- prunes old backups based on retention

Requirement:

- PostgreSQL tools must be installed and available in `PATH`

Optional environment variable in `backend\.env`:

```env
BACKUP_RETENTION_DAYS=30
```

## Windows Scheduled Backup

Use:

- [install_backup_task.bat](/home/grejoy/Projects/pharma-pos-ai/install_backup_task.bat)

What it does:

- creates a Windows Task Scheduler job
- runs the backup every day at 8:00 PM
- writes output to `backups\backup.log`

## Windows Restore

Use:

- [restore.bat](/home/grejoy/Projects/pharma-pos-ai/restore.bat)

Example:

```bat
restore.bat backups\pharma_pos_backup_20260407_154500.dump
```

Important:

- it asks for confirmation
- it overwrites the current database contents

## Linux Backup

Use:

- [backup_postgres.sh](/home/grejoy/Projects/pharma-pos-ai/scripts/backup_postgres.sh)

Example:

```bash
cd /home/grejoy/Projects/pharma-pos-ai
bash scripts/backup_postgres.sh
```

Behavior:

- creates a timestamped `.dump` file in [backups](/home/grejoy/Projects/pharma-pos-ai/backups)
- updates `backups/latest_backup.txt` with the newest backup path
- deletes old dump files beyond the retention window

Optional environment variable:

```env
BACKUP_RETENTION_DAYS=30
```

## Linux Scheduled Backup

Use:

- [install_backup_cron.sh](/home/grejoy/Projects/pharma-pos-ai/scripts/install_backup_cron.sh)

Example:

```bash
cd /home/grejoy/Projects/pharma-pos-ai
bash scripts/install_backup_cron.sh
```

Default schedule:

- every day at 8:00 PM

Optional environment variable:

```env
BACKUP_CRON_SCHEDULE=0 20 * * *
```

## Linux Restore

Use:

- [restore_postgres.sh](/home/grejoy/Projects/pharma-pos-ai/scripts/restore_postgres.sh)

Example:

```bash
cd /home/grejoy/Projects/pharma-pos-ai
bash scripts/restore_postgres.sh backups/pharma_pos_backup_20260407_154500.dump
```

## Environment Source

The backup and restore scripts use values from:

- [backend/.env](/home/grejoy/Projects/pharma-pos-ai/backend/.env)

Expected variables:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=pharma_pos
POSTGRES_USER=pharma_user
POSTGRES_PASSWORD=your_password_here
```

## Before Running Restore

Always do this first:

1. create a fresh backup of the current state
2. confirm all users are out of the system
3. stop the backend if possible
4. restore
5. start backend again
6. test login, products, sales, and dashboard

## Restore Drill Recording

Do not test restores against the live pharmacy database unless there is a real recovery incident and management has approved it.

For normal readiness checks:

1. copy a recent `.dump` file to a test machine, staging database, or technician laptop
2. restore into the test database
3. verify login works
4. verify latest sales are visible
5. verify product and batch stock counts open correctly
6. verify audit logs open
7. open Settings in the live system
8. record the restore drill result under Restore Drill Readiness

The app stores:

- drill status
- backup path
- restore target
- technician notes
- tested timestamp
- user who recorded the drill

`RESTORE_DRILL_MAX_AGE_DAYS` controls how long a successful drill counts as recent. The default is 90 days.

## Recommended Client Practice

For each live client:

- keep backups on the main pharmacy PC
- copy weekly backups to external drive
- keep at least 14 to 30 days of backups
- document who is responsible for checking backups

## Current Product Support

The system now supports:

- backup status visibility from the admin settings area
- manual backup trigger from the app for admins/managers
- restore drill readiness status
- non-destructive restore drill recording
- local diagnostics visibility from the admin settings area
- Windows scheduled backup helper via `install_backup_task.bat`

Still recommended next:

- installer-driven Task Scheduler setup by default
- post-restore integrity check script for technicians
- explicit backup warning banners when backups are stale

## Related Operational Controls

Backups are only one part of dependable pharmacy operation.
Also review:

- [Go-Live Checklist](/home/grejoy/Projects/pharma-pos-ai/docs/GO_LIVE_CHECKLIST.md)
- [Missing Operational Controls Checklist](/home/grejoy/Projects/pharma-pos-ai/docs/MISSING_OPERATIONAL_CONTROLS_CHECKLIST.md)
- [Client User Guide](/home/grejoy/Projects/pharma-pos-ai/docs/CLIENT_USER_GUIDE.md)
