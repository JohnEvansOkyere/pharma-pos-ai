# Incident Response

## Sync Failure

Symptoms:

- sync pending count grows
- failed sync count grows
- last sent timestamp stale
- cloud dashboard stale

Actions:

1. Confirm local internet connectivity.
2. Confirm cloud ingest URL and token.
3. Review `sync_events.last_error`.
4. Retry manually through system sync endpoint if appropriate.
5. Do not delete sync events.
6. Escalate repeated payload or identity errors.

## Projection Failure

Symptoms:

- projection failed count grows
- reconciliation reports projection failures
- cloud facts/snapshots are stale

Actions:

1. Review `ingested_sync_events.projection_error`.
2. Fix projector bug or bad event handling if needed.
3. Use admin repair `retry_failed_projections`.
4. Confirm reconciliation issue clears.
5. Keep audit record.

## Stock Mismatch

Symptoms:

- product total does not equal batch sum
- negative product or batch stock
- branch report totals look wrong

Actions:

1. Determine whether mismatch is local operational data or cloud projection data.
2. For local branch data, use stock take or stock adjustment with reason.
3. For supported cloud read-model mismatch, admin may run reconciliation repair.
4. Do not manually patch local stock without an auditable workflow.

## Backup Failure

Symptoms:

- backup is stale
- backup trigger fails
- latest backup file missing

Actions:

1. Check database credentials.
2. Check backup directory permissions.
3. Check script availability.
4. Run manual backup.
5. Confirm latest backup status updates.
6. Schedule repair before client handoff.

## Audit Integrity Incident

Tamper-evident audit chaining is not yet implemented. Until it exists, treat suspicious audit gaps as high risk.

Recommended handling:

1. Export current audit logs.
2. Preserve database backup.
3. Review database access history where available.
4. Compare sales, stock movements, and sync events.
5. Document findings.
