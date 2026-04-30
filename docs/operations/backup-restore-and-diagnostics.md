# Backup, Restore, And Diagnostics

## Backup System

System operations expose:

- backup status
- manual backup trigger
- restore drill readiness
- restore drill recording
- diagnostics

Backup scripts exist for Windows and Linux paths. The system reads latest backup metadata from the backup directory and status file.

## Backup Status

Backup status reports:

- platform
- backup directory
- latest backup path
- latest backup existence
- latest backup time
- latest backup size
- backup age in hours
- whether backup is recent
- retention days
- trigger availability
- schedule helper availability

## Diagnostics

Diagnostics include:

- platform
- app version
- environment
- database backend
- database connectivity
- scheduler enabled/running
- scheduler job count
- latest backup state
- frontend build availability
- sync enabled/configured
- sync pending/failed/sent counts
- last sent sync timestamp

## Restore Discipline

A backup is not real until restore has been tested.

The system now records non-destructive restore drills. It does not automatically restore over the live pharmacy database.

Restore drill status reports:

- latest backup status
- last recorded restore drill
- whether the latest backup path matches the last passed drill
- maximum acceptable drill age
- recovery-ready status
- checklist results for backup existence, backup recency, recent restore drill, and latest-backup-tested state

Restore drill records include:

- passed or failed status
- backup path
- backup timestamp and size when available
- restore target
- technician notes
- verification summary
- user who recorded the drill
- tested timestamp

Production rollout should include:

- documented restore procedure
- restore test on a separate machine or separate database
- verification of sale, stock, user, and audit data after restore
- recovery time expectation
- who is allowed to perform restore
- a recorded restore drill in Settings before handoff

See `docs/BACKUP_RESTORE_GUIDE.md` for the detailed existing guide.
