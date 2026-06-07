# System Overview

## Product Purpose

This project is a local-first pharmaceutical POS system for pharmacy operations. The primary installed product runs inside a pharmacy with a local backend and a local PostgreSQL database. The system supports POS sales, product and batch inventory, expiry tracking, stock controls, supplier management, reporting, audit logs, backups, and manager-facing AI reporting.

The strategic direction is one isolated operational deployment per pharmacy
organization plus a central reporting plane:

- offline pharmacies run the backend and PostgreSQL locally
- hosted pharmacies use a dedicated Render backend and paid Render Postgres instance
- branches in one organization share its database; organizations never share an operational database
- operational events are written to a transactional sync outbox
- the tenant backend uploads approved business events to a central ingestion API
- the cloud side projects those events into reporting read models
- managers can view multi-branch cloud dashboards and use AI over approved aggregate reporting data

The existing Supabase project is the central reporting/control-plane database,
not a shared operational POS database. See
[Hosted Tenant Topology And Backup](hosted-tenant-topology-and-backup.md).

## Current System Shape

```text
Pharmacy workstation/browser
        |
        | React frontend
        v
Tenant FastAPI backend (local or hosted)
        |
        | SQLAlchemy transactions
        v
Dedicated tenant PostgreSQL database
        |
        | transactional outbox + scheduled upload
        v
Central ingestion API
        |
        | idempotent ingestion + projection
        v
Supabase Postgres reporting database
        |
        | cloud dashboard + AI manager assistant
        v
Manager reporting experience
```

## Core Modules

- Backend API: FastAPI application under `backend/app`.
- Frontend UI: React/Vite/TypeScript application under `frontend/src`.
- Database: PostgreSQL with SQLAlchemy ORM and Alembic migrations.
- Auth: JWT bearer authentication with roles and granular permissions.
- Local POS: sales, product search, cart, batch-aware stock reduction, receipt-level sale records.
- Inventory: products, batches, FEFO sale allocation, stock adjustments, stock takes, movement ledger.
- Reporting: local dashboard plus cloud reporting endpoints.
- Hybrid sync: local `sync_events`, cloud `ingested_sync_events`, projection tables.
- AI: read-only manager chat and weekly manager reports over cloud reporting data.
- Operations: backup status, manual backup trigger, diagnostics, audit log viewer/export.

## Production Principles

- Local branch operation must remain dependable.
- Sales and stock writes must be transaction-safe.
- Dispensing stock should be batch-aware and FEFO by default.
- Cloud reporting is a derived read model, not the source of truth for local dispensing.
- AI must be read-only and must not approve dispensing, alter stock, or provide clinical advice.
- Sensitive operations must be auditable, and new audit rows are tamper-evident through per-organization hash chaining.
- Admin repair tooling must be scoped and controlled.
- Environment secrets must remain outside the repository.

## Source Of Truth Boundaries

Tenant operational source of truth:

- sales documents
- product and batch stock used for dispensing
- stock adjustments and stock take corrections
- tenant sync outbox state
- tenant backups

Cloud source of truth:

- accepted uploaded branch events
- projected reporting facts and snapshots
- cloud reconciliation workflow state
- AI weekly reports and delivery records
- tenant AI provider policy

Cloud reporting read models must never silently overwrite local branch dispensing data. Repairs currently implemented affect cloud read models only.

## Current Important Limitations

- True offline-first browser storage is not implemented; the frontend requires a reachable local backend.
- Cloud sync is event-upload based and currently focused on reporting projections, not full bidirectional operational sync.
- AI external providers are optional and fall back to deterministic responses when unavailable.
- Audit logging now has tamper-evident hash chaining for new `AuditService.log` entries; legacy rows remain unsealed.
- Controlled-drug and prescription safety fields exist in the product and sale model, but deeper server-side enforcement remains a hardening priority.
