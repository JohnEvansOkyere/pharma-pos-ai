# Hybrid Cloud Architecture

## Goal

The hybrid cloud design lets each pharmacy branch operate locally while creating a cloud reporting layer for owners and managers.

The local branch remains operationally independent. The cloud layer receives event streams and builds reporting views. This keeps internet failure from blocking dispensing and sales.

## Tenant Model

The system now models:

- organization: one pharmacy client/business tenant
- branch: one physical pharmacy branch under an organization
- device: one local branch machine, till, or server

Important tables:

- `organizations`
- `branches`
- `devices`
- tenant-aware columns on operational and cloud tables

The expected scaled deployment is many organizations, each with one or more branches, each branch having one or more registered devices.

## Event Flow

```text
Local write transaction
  - sale
  - stock adjustment
  - stock take
  - product/batch change
        |
        v
sync_events row written in the same transaction
        |
        v
scheduled or manual upload
        |
        v
cloud ingestion validates identity, sequence, and payload hash
        |
        v
ingested_sync_events
        |
        v
projection service builds reporting tables
        |
        v
cloud dashboard, reconciliation, AI reports
```

## Local Outbox

Local events are stored in `sync_events`.

Important behavior:

- event ids are UUIDs
- local sequence numbers are durable and allocated through `sync_event_counters`
- payloads are JSON-safe and hashed
- upload status tracks `pending`, `sending`, `sent`, and `failed`
- retries are bounded by configuration
- events are ordered by local sequence number for upload

This pattern is important because the business write and the sync event are committed together. If the sale succeeds, the sync event exists. If the transaction rolls back, no sync event is emitted.

## Cloud Ingestion

Cloud ingestion stores accepted events in `ingested_sync_events`.

Important behavior:

- `event_id` is unique
- device sequence is unique per source device
- payload hash supports duplicate detection
- duplicate deliveries increment duplicate count instead of creating duplicate facts
- projection failures are stored on the event for later review and retry

## Cloud Projection

The cloud projection service turns accepted events into read models:

- `cloud_sale_facts`: sales reporting facts
- `cloud_inventory_movement_facts`: stock movement facts
- `cloud_product_snapshots`: current product state per branch
- `cloud_batch_snapshots`: current batch state per branch

The projection layer is idempotent at the fact level where unique constraints exist. Projection failures are captured on `ingested_sync_events.projection_error`.

## Cloud Reconciliation

Cloud reconciliation checks detect reporting data quality issues such as:

- failed projections
- negative product stock
- negative batch quantity
- product total mismatch against batch totals
- orphan batch snapshots

Managers/admins can acknowledge and resolve generated issues. Admins can run controlled repairs for currently supported issue types.

Current controlled repairs:

- retry failed projections
- rebuild stale product stock total from non-quarantined batch snapshots

Current repair boundaries:

- repair actions are admin-only
- repairs are tenant/branch scoped
- repairs are audited
- repairs modify cloud reporting read models only
- local branch source data is not changed by cloud repair

## Supabase Postgres Direction

Supabase Postgres is the cloud database target. The implementation should treat Supabase as PostgreSQL with managed hosting, backups, connection limits, and platform policies.

Production expectations:

- use service-side credentials only in backend/cloud services
- keep Supabase keys out of frontend code unless a specific public anon-key use case is designed
- enforce tenant scoping at application level and, where practical, database policy level
- use migrations rather than manual schema editing
- monitor connection count, slow queries, storage, and backup status
- keep ingestion and projection idempotent

## What This Is Not Yet

This is not yet full bidirectional sync. The current architecture is cloud reporting and manager intelligence from branch events. Pushing cloud edits back into branch operational databases should be treated as a separate, higher-risk phase.
