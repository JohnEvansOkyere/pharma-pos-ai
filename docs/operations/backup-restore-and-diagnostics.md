# Backup, Restore, And Diagnostics

## Backup System

System operations expose:

- backup status
- manual backup trigger
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

Production rollout should include:

- documented restore procedure
- restore test on a separate machine or separate database
- verification of sale, stock, user, and audit data after restore
- recovery time expectation
- who is allowed to perform restore

See `docs/BACKUP_RESTORE_GUIDE.md` for the detailed existing guide.
