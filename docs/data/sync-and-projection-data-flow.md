# Sync And Projection Data Flow

## Local Outbox Tables

`sync_events` stores branch events waiting for cloud upload.

Fields that matter:

- `event_id`: UUID identity
- `organization_id`
- `branch_id`
- `source_device_id`
- `local_sequence_number`
- `event_type`
- `aggregate_type`
- `aggregate_id`
- `schema_version`
- `payload`
- `payload_hash`
- `status`
- `retry_count`
- `last_error`

`sync_event_counters` allocates durable sequence numbers.

## Upload Worker

`SyncUploadService` uploads pending and failed events when cloud sync is enabled.

Behavior:

- skips when disabled
- skips when ingest URL is missing
- resolves organization, branch, and device identity
- sends JSON payload to configured ingestion URL
- uses bearer token when configured
- marks successful uploads as sent
- records HTTP or network errors on the event
- increments retry counts

## Ingestion Table

`ingested_sync_events` stores cloud-accepted events.

Important fields:

- event id
- organization/branch/device
- device local sequence
- event type
- payload hash
- duplicate count
- projection status
- projection error

Duplicate delivery should not duplicate reporting facts.

## Projection Tables

Projection turns events into reporting read models:

- sale facts
- inventory movement facts
- product snapshots
- batch snapshots

These tables exist for cloud reporting, reconciliation, and AI. They should not be used to drive local branch dispensing decisions.

## Reconciliation

Reconciliation compares projected cloud data for signs of corruption or projection drift.

Issue examples:

- failed projection count
- negative stock
- batch/product total mismatch
- orphan batch snapshot

Managers can acknowledge and resolve issues. Admins can run supported repairs.

## Current Repair Tooling

Admin-only repairs:

- retry failed projections
- rebuild product total stock from batch snapshots

Both repair types are audited. Both operate on cloud read models only.
