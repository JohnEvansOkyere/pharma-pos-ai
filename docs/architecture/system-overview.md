# System Overview

## Product Purpose

This project is a local-first pharmaceutical POS system for pharmacy operations. The primary installed product runs inside a pharmacy with a local backend and a local PostgreSQL database. The system supports POS sales, product and batch inventory, expiry tracking, stock controls, supplier management, reporting, audit logs, backups, and manager-facing AI reporting.

The strategic direction is hybrid cloud:

- each pharmacy branch keeps working locally even when internet is unavailable
- branch events are written to a local sync outbox
- the local backend uploads approved business events to a cloud ingestion API when connectivity exists
- the cloud side projects those events into reporting read models
- managers can view multi-branch cloud dashboards and use AI over approved aggregate reporting data

The cloud database target discussed for production is Supabase Postgres. Neon can support similar Postgres patterns, but Supabase is the primary cloud database target for this product direction.

## Current System Shape

```text
Pharmacy workstation/browser
        |
        | React frontend
        v
Local FastAPI backend
        |
        | SQLAlchemy transactions
        v
Local PostgreSQL database
        |
        | optional scheduled sync upload
        v
Cloud ingestion API / cloud backend
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
- Sensitive operations must be auditable.
- Admin repair tooling must be scoped and controlled.
- Environment secrets must remain outside the repository.

## Source Of Truth Boundaries

Local source of truth:

- sales documents
- product and batch stock used for dispensing
- stock adjustments and stock take corrections
- local sync outbox state
- branch backups

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
- Audit logging exists, but tamper-evident hash chaining is still planned.
- Controlled-drug and prescription safety fields exist in the product and sale model, but deeper server-side enforcement remains a hardening priority.
