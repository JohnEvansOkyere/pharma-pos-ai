# Cloud Operations

## Cloud Sync Controls

Local sync can be enabled or disabled with environment settings.

Key settings:

- `CLOUD_SYNC_ENABLED`
- `CLOUD_SYNC_INGEST_URL`
- `CLOUD_SYNC_API_TOKEN`
- `CLOUD_SYNC_DEVICE_UID`
- `CLOUD_SYNC_ORGANIZATION_ID`
- `CLOUD_SYNC_BRANCH_ID`
- `CLOUD_SYNC_BATCH_SIZE`
- `CLOUD_SYNC_MAX_RETRIES`
- `CLOUD_SYNC_INTERVAL_MINUTES`

## Sync Monitoring

Monitor:

- pending sync events
- failed sync events
- sent sync events
- last sent timestamp
- upload errors
- projection failures
- duplicate counts
- reconciliation issues

## Cloud Reporting Maintenance

Cloud reporting maintenance includes:

- running projection for pending ingested events
- reviewing projection failures
- using reconciliation repair only where supported
- keeping repairs audited
- avoiding manual database fixes unless documented as incident response

## Supabase Operations

For Supabase Postgres:

- monitor database size
- monitor connection count
- monitor slow queries
- configure backups and retention
- restrict service keys
- rotate credentials
- use migrations
- protect direct production database access

## Cloud Failure Mode

If cloud is down:

- local POS should continue
- local outbox accumulates pending events
- manager cloud reports become stale
- AI cloud reporting answers may become stale or unavailable
- sync catches up when cloud returns
