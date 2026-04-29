# Hybrid Cloud Production Architecture Plan

## Purpose

This document defines the production architecture direction for turning this project into a scalable pharmacy POS product for city pharmacies.

The target product is a hybrid local-first system:

- pharmacy branches continue selling and dispensing locally when internet is unavailable
- cloud services provide multi-client management, backups, reporting, monitoring, AI assistance, and future multi-branch coordination
- database correctness, auditability, recoverability, and security are treated as core product features

This document is the working plan agents should check before making major architecture, database, sync, security, or AI changes.

## Product Position

The product will support many pharmacy clients.

Each client may start with one branch, but the system must be designed so the same client can later operate multiple branches without rewriting the core database, authorization, sync, or reporting model.

The product model is:

```text
many clients
each client has one or more branches
each branch has one or more devices/tills
each branch can operate locally
cloud aggregates and manages the client estate
```

The first implementation target is:

```text
many clients
one branch per client
local branch operation
cloud sync for backup, reporting, monitoring, and AI insights
```

The architecture must not be limited to a single pharmacy owner or a single branch.

## Non-Negotiable System Principles

1. Critical POS workflows must not depend on internet connectivity.
2. A completed sale must be ACID-safe.
3. Inventory must be batch-aware.
4. FEFO must be the default stock deduction policy.
5. Prescription-only and controlled-drug rules must be enforced by backend logic, not frontend UI only.
6. Critical writes must produce audit records.
7. Historical records must not be destructively edited to correct business events.
8. Cloud sync must be idempotent.
9. AI must not mutate stock, approve dispensing, override pharmacy rules, or make clinical decisions.
10. The frontend must never hold privileged database credentials.

## Deployment Model

### Local Branch Runtime

Each branch runs a local system:

```text
Branch POS Frontend
        |
Local Backend API
        |
Local PostgreSQL Database
        |
Local Backup + Sync Worker
```

The branch runtime owns daily operational continuity:

- login for local staff
- POS cart and checkout
- sale creation
- payment recording
- stock deduction
- batch selection
- receipt printing
- refunds and reversals
- local reports needed during the workday
- local audit logging
- local backup

### Cloud Runtime

The cloud platform provides central services:

```text
Cloud API
        |
Cloud PostgreSQL Database
        |
Cloud Dashboard
        |
AI Assistant Service
        |
Monitoring + Backup + Support Tools
```

Cloud services own:

- tenant and branch registry
- device registry
- license state
- synced event ingestion
- centralized reporting
- owner/manager dashboard
- AI manager assistant
- offsite backups
- sync health monitoring
- support diagnostics
- future centralized catalog management

### Cloud Database Provider Direction

The cloud database is Supabase Postgres.

Implementation rule:

- Supabase is the managed cloud PostgreSQL provider.
- Critical pharmacy writes still go through backend-controlled APIs or Supabase Edge Functions, not direct browser writes.
- Supabase service-role credentials must stay server-side only.
- RLS must be enabled on exposed tenant-owned tables as defense in depth.
- Device sync should submit events to an ingestion API backed by Supabase Postgres.

Architecture rule:

```text
Pharmacy-critical writes go through the backend API.
Frontend clients do not write directly to critical database tables.
```

Even if Supabase is selected, service keys must remain server-side only.

## Tenant, Branch, And Device Model

The cloud system must use a multi-tenant model from the beginning.

Required hierarchy:

```text
organization
  branch
    device
    user assignment
    sales
    inventory
    audit logs
```

Minimum identifiers:

- `organization_id`: identifies the pharmacy client/business
- `branch_id`: identifies the physical branch
- `device_id`: identifies a registered local machine/till/server
- `user_id`: identifies the actor
- `sync_event_id`: identifies the sync envelope that carried a change

Most business tables must include:

```text
organization_id
branch_id
created_at
updated_at
created_by
updated_by
source_device_id
```

Cloud tenant isolation is mandatory.

For shared multi-tenant cloud databases:

- every tenant-owned row must carry `organization_id`
- tenant access must be enforced by backend authorization
- if Supabase direct API exposure is used for non-critical reads, RLS must be enabled and tested
- no cross-tenant query may depend only on frontend filtering

## Database Strategy

### Local Database

Production branch installations should use PostgreSQL as the local database.

SQLite is acceptable only for development, demos, or explicitly approved very small pilots. It is not the standard target for city pharmacy deployments.

Reasons for PostgreSQL locally:

- stronger concurrent transaction behavior
- better crash recovery
- better multi-user operation
- reliable locking and isolation controls
- mature backup and restore tooling
- closer parity with cloud PostgreSQL

### Cloud Database

The cloud database should also be PostgreSQL.

Reasons:

- common schema concepts across local and cloud
- easier data validation and migration
- mature ACID guarantees
- support for constraints, indexes, views, materialized views, row-level security, JSONB, and robust transaction semantics
- easier future reporting and AI retrieval patterns

### Database-Per-Client Vs Shared Multi-Tenant

Default strategy:

```text
shared cloud database
strict tenant isolation by organization_id
backend authorization and optional RLS defense in depth
```

Rationale:

- simpler operations at current stage
- easier product updates
- easier shared reporting infrastructure
- lower cost
- faster onboarding

Database-per-client may be offered later for enterprise clients that require stronger isolation, custom retention, custom compliance, or dedicated infrastructure.

## ACID Rules For Critical Workflows

### Sale Completion Transaction

A sale is complete only when all related writes commit together.

The sale completion transaction must include:

- sale header creation
- sale item creation
- payment record creation
- batch quantity deduction
- inventory movement creation
- prescription/control validation result
- audit log entry
- local sync outbox event

All writes must commit or all writes must roll back.

Invalid partial states:

- sale exists without sale items
- sale exists without payment state
- stock deducted without sale record
- payment recorded without stock movement
- sync event created without the business records it references
- receipt printed for a transaction that failed to commit

### Refund And Reversal Transaction

Refunds must use reversal records. Past sales must not be deleted to represent refunds.

Refund transaction must include:

- refund header
- refund items
- payment reversal or refund payment record
- inventory movement if stock is returned to sellable stock
- batch-level returned quantity when applicable
- audit log
- approval record where required
- local sync outbox event

Returned products must not automatically become sellable stock.

Return-to-stock must depend on:

- product type
- batch condition
- expiry status
- whether packaging is intact
- controlled-drug rules
- manager/pharmacist approval where required

### Stock Adjustment Transaction

Stock adjustments must be explicit business events.

Adjustment transaction must include:

- adjustment header
- adjustment line items
- reason code
- batch reference
- inventory movement
- approval user when required
- audit log
- local sync outbox event

Direct silent edits to stock quantity are not allowed.

### User And Permission Transaction

User and role changes must be auditable.

Transaction must include:

- user or role mutation
- actor identity
- permission changed
- old role/permission state
- new role/permission state
- audit log
- sync event when cloud or branch propagation is required

## Inventory Model

Inventory must be movement-based and batch-aware.

Do not rely on a single mutable `product.stock_quantity` as the source of truth.

Required inventory concepts:

- product
- product variant or package unit where needed
- batch
- batch expiry date
- batch received quantity
- batch current quantity
- inventory movement
- stock adjustment
- supplier receipt
- sale deduction
- refund return
- expiry write-off
- damage/loss write-off
- branch transfer, later phase

Inventory movement types:

```text
stock_received
sale_dispensed
sale_reversed
refund_returned_sellable
refund_returned_unsellable
stock_adjustment_positive
stock_adjustment_negative
expiry_write_off
damage_write_off
batch_recall_hold
branch_transfer_out
branch_transfer_in
```

Each movement must include:

```text
organization_id
branch_id
product_id
batch_id
quantity_delta
movement_type
source_document_type
source_document_id
reason_code
created_by
created_at
source_device_id
```

Current stock may be stored as a maintained balance for speed, but movement records remain the audit source.

If maintained balances are used:

- updates must occur inside the same transaction as the movement
- database constraints must prevent invalid negative stock unless an explicit audited policy allows it
- reconciliation jobs must compare balances against movements

## FEFO And Batch Policy

FEFO means first-expiry-first-out.

Default dispensing behavior:

```text
select sellable batches
exclude expired batches
exclude recalled/held batches
order by expiry date ascending
deduct from earliest expiry first
```

Manual batch override is allowed only when:

- the user has permission
- the selected batch is legally sellable
- the user provides a reason
- the override is audit logged

Expired stock must not be sold.

Near-expiry warnings remain deterministic backend logic.

AI may explain expiry risk, but AI does not decide whether a batch is expired, sellable, or blocked.

## Prescription And Controlled-Drug Controls

The backend must enforce product controls.

Product control classifications should include:

```text
general_sale
pharmacy_medicine
prescription_only
controlled_drug
restricted_supply
```

For restricted products, sales must support:

- pharmacist approval
- prescription reference
- prescriber information where required
- patient/customer reference where required
- quantity limits
- controlled-drug register entries
- override reason
- approval audit log

Frontend prompts are not enforcement.

Server-side sale validation must block illegal or incomplete restricted sales.

## Audit Logging

Audit logging is a first-class product feature.

Audit logs must be append-only.

Critical audited actions:

- login success and failure
- user creation
- role and permission changes
- sale completion
- sale void
- refund
- price override
- discount override
- stock receipt
- stock adjustment
- batch override
- expired stock write-off
- controlled-drug sale
- prescription override
- backup created
- restore performed
- sync event accepted
- sync event rejected
- device registered
- license state changed
- AI recommendation shown
- AI-assisted action approved

Audit log minimum fields:

```text
audit_id
organization_id
branch_id
actor_user_id
actor_role
device_id
action_type
entity_type
entity_id
old_value_json
new_value_json
reason
approval_user_id
request_id
created_at
source_ip_or_machine
```

Audit logs must not be editable by normal application workflows.

If correction is needed, create a new audit event explaining the correction.

## Sync Architecture

The sync design must use an outbox/event model.

Local business transactions write local data and a sync event in the same local database transaction.

Flow:

```text
business transaction starts
business tables are updated
audit log is written
sync outbox event is written
transaction commits
sync worker uploads unsynced events
cloud validates and stores event
local event is marked synced
```

Do not begin with table-diff sync.

### Sync Event Requirements

Each event must include:

```text
event_id
organization_id
branch_id
device_id
local_sequence_number
event_type
schema_version
payload
payload_hash
created_at_local
sent_at
received_at_cloud
idempotency_key
```

Cloud ingestion must be idempotent.

Duplicate delivery must not double-count:

- sales
- payments
- stock movements
- refunds
- audit logs

### Data Ownership Rules

Branch-owned data:

- sales
- local stock movements
- local refunds
- local audit events
- local backup events
- local till/shift events

Cloud-owned data:

- tenant registry
- branch registry
- device registry
- license state
- subscription state
- cloud dashboard users
- AI assistant configuration

Shared or coordinated data:

- product catalog
- supplier catalog
- user provisioning
- price lists
- branch configuration

Shared data must have explicit conflict rules before implementation.

## Conflict Management

Avoid silent overwrite.

Conflict policy:

- append-only business events do not get overwritten
- corrections happen through reversal or adjustment events
- local branch stock remains authoritative for that branch's live operations
- cloud aggregates branch stock from synced events
- cloud does not silently replace local branch stock
- cloud-originated config changes must be versioned
- failed sync events must remain visible until resolved

Every unresolved conflict must have:

```text
conflict_id
event_id
conflict_type
detected_at
resolution_status
resolved_by
resolved_at
resolution_notes
```

## Backup, Restore, RPO, And RTO

Backups must be designed and tested before production rollout.

### Local Backup

Each branch must support:

- scheduled local PostgreSQL backup
- encrypted backup file
- backup to external drive or network path where available
- backup status in Settings or diagnostics
- manual backup trigger for technicians
- restore procedure documented and tested

Local restore target:

```text
RPO: no more than one business day for baseline deployments
RTO: restore branch POS operation within one business day for baseline deployments
```

For higher-tier clients, target:

```text
RPO: 15 minutes to 1 hour
RTO: under 2 hours
```

The product must clearly document which tier is being delivered.

### Cloud Backup

Cloud PostgreSQL must have:

- managed daily backups at minimum
- point-in-time recovery for production plans where budget allows
- periodic logical exports for independent recovery
- restore drills on staging copies
- restricted access to backup credentials

Backups are not complete until restore has been tested.

## Security Architecture

### Authentication

Public self-registration must not exist in release builds.

User provisioning must be admin-controlled.

Required account controls:

- strong passwords
- disabled demo credentials in release builds
- role-based access control
- optional MFA for cloud owners/admins
- account disablement
- password reset flow controlled by admin or secure cloud process
- session expiration
- audit logging for auth events

### Authorization

Roles should be explicit:

```text
owner
branch_manager
pharmacist
cashier
inventory_clerk
auditor
support_technician
```

Permissions must be granular:

```text
can_sell
can_refund
can_void_sale
can_override_price
can_apply_discount
can_adjust_stock
can_receive_stock
can_write_off_stock
can_sell_prescription_only
can_sell_controlled_drug
can_override_batch
can_manage_users
can_view_reports
can_export_data
can_restore_backup
can_manage_devices
can_manage_license
```

Backend APIs must enforce permissions.

Frontend route hiding is not authorization.

Cloud report APIs must enforce tenant scope on the backend. A user assigned to
an organization may only query that organization's cloud reporting data.
If the user is assigned to a specific branch, cloud report APIs must limit that
user to that branch even when a branch filter is omitted.
Platform-level admin access is explicit and reserved for admin users without an
organization assignment during the current transition period.

### Secrets And Keys

Rules:

- no service keys in frontend code
- no production secrets committed to git
- local secrets stored in environment or protected config
- branch device credentials rotateable
- sync requests signed or authenticated
- database admin credentials restricted to setup/support use

### Data Privacy

Patient and prescription data is sensitive.

Rules:

- collect minimum necessary patient data
- restrict access by role
- audit access to sensitive records where practical
- do not send patient-identifiable data to AI by default
- anonymize or aggregate AI context where possible
- document retention rules before production rollout

## Cash, Shift, And Reconciliation

The POS must eventually include cash accountability.

Required concepts:

- cashier shift/session
- opening cash
- sales by payment method
- refunds by payment method
- cash drops
- expected cash
- counted cash
- variance
- closeout approval
- audit log for closeout

Historical sale items must snapshot:

- product name at sale time
- batch number
- quantity
- unit price
- discount
- tax/VAT state if applicable
- cost basis where used for margin reporting

Old sales must not depend on current product prices.

## Database Migration Practices

All schema changes must use versioned migrations.

Migration rules:

- never manually patch production schema without recording a migration
- test migrations on a copy before production rollout
- take a backup before risky migrations
- avoid destructive migrations in one step
- prefer expand/contract migrations for critical tables
- keep seed/demo data separate from production migrations
- migrations must preserve auditability
- migrations touching sales, inventory, users, pricing, or auth require focused tests

Expand/contract example:

```text
1. add nullable new column
2. deploy code that writes both old and new fields
3. backfill existing rows
4. deploy code that reads new field
5. enforce NOT NULL or remove old field later
```

## Reporting And Analytics

Reporting must not block POS operations.

Local reports should cover urgent branch needs.

Cloud reports should cover owner and manager needs:

- branch sales
- gross margin
- stock by branch
- low stock
- expiry risk
- dead stock
- fast-moving products
- refund analysis
- cashier performance
- controlled-drug activity
- sync health
- backup health
- audit log review

Heavy analytical queries should run in the cloud or against read-optimized tables/views, not inside the POS checkout transaction path.

## AI Architecture

AI is for operational intelligence, not dispensing authority.

Core rule:

```text
Rules engine decides.
AI explains, summarizes, predicts, and assists.
```

Deterministic backend logic owns:

- low-stock thresholds
- expiry detection
- expired-stock blocking
- FEFO batch selection
- prescription-only enforcement
- controlled-drug enforcement
- stock movement creation
- sale legality
- audit logging

AI may provide:

- manager briefing
- natural-language reporting
- reorder suggestions
- stockout forecast explanation
- expiry risk explanation
- unusual refund explanation
- suspicious stock adjustment summary
- duplicate product detection suggestions
- catalog cleanup suggestions
- supplier order draft

AI must not:

- diagnose patients
- recommend medicine as clinical advice
- approve controlled-drug sales
- override prescription rules
- mutate stock directly
- create final purchase orders without human approval
- view patient-identifiable data unless explicitly designed and approved
- run arbitrary SQL against production

### AI Tool Pattern

The AI assistant must call approved backend tools.

Approved tool examples:

```text
get_sales_summary
get_low_stock_items
get_expiring_batches
get_inventory_velocity
get_stockout_forecast
get_refund_anomalies
get_controlled_drug_summary
get_reorder_recommendations
get_duplicate_product_candidates
draft_purchase_order
```

Write pattern:

```text
AI drafts
manager reviews
manager approves
backend executes
audit log records
```

The first AI feature should be:

```text
AI Manager Briefing + Natural Language Reports
```

This gives strong client value without risking checkout correctness.

## Cloud Dashboard

The cloud dashboard is for owners, managers, and support users.

Required dashboard areas:

- branch overview
- sales performance
- inventory health
- expiry risk
- low-stock and stockout risk
- refund and void review
- audit log viewer
- backup status
- sync status
- device health
- license status
- AI assistant chat

The AI assistant must cite the data category behind its answer, such as sales period, branch, product group, or report source.

The assistant must not pretend to know data that was not retrieved from tools.

## Operational Diagnostics And Support

Every branch install should expose support diagnostics:

- local backend status
- local database connectivity
- database size
- last successful backup
- last failed backup
- pending sync event count
- failed sync event count
- last successful cloud sync
- app version
- schema migration version
- device ID
- license status
- local machine clock status where possible

Support exports should avoid unnecessary patient data.

## Rollout Phases

### Phase 1: Local Production Hardening

Goal:

```text
single-branch local POS safe enough for real operational pilots
```

Scope:

- admin-controlled users
- stronger role permissions
- transaction-safe sales
- batch-aware inventory
- FEFO stock deduction
- refund/reversal model
- audit logs for critical writes
- backup and restore workflow
- local PostgreSQL standardization
- focused regression tests

### Phase 2: Cloud Foundation

Goal:

```text
cloud platform can register clients, branches, and devices
```

Scope:

- cloud PostgreSQL schema
- organization/branch/device model
- cloud auth/admin model
- secure device registration
- license state
- tenant isolation
- initial cloud dashboard shell

### Phase 3: Outbox Sync

Goal:

```text
local branch sends append-only events to cloud reliably
```

Scope:

- local sync outbox
- sync worker
- cloud event ingestion API
- idempotency keys
- sync health dashboard
- retry and failure handling
- conflict logging

### Phase 4: Cloud Reporting

Goal:

```text
owners can view trusted branch data in the cloud
```

Scope:

- sales reports
- stock reports
- expiry reports
- low-stock reports
- refund reports
- audit log viewer
- backup and sync status

### Phase 5: AI Manager Assistant

Goal:

```text
AI summarizes and explains operational data through approved tools
```

Scope:

- AI chat interface in cloud dashboard
- manager briefing
- natural-language reports
- reorder suggestions
- expiry risk explanations
- anomaly explanations
- AI action audit logs

### Phase 6: Multi-Branch Workflows

Goal:

```text
clients with multiple branches can coordinate safely
```

Scope:

- branch comparison reports
- centralized catalog distribution
- controlled branch configuration sync
- inter-branch transfer workflow
- central purchasing workflow
- branch-level permissions

## Engineering Checklist For Future Work

Before changing auth, sales, inventory, sync, pricing, backups, or AI, check:

- does this preserve local POS operation without internet?
- does this preserve ACID behavior?
- does this create an audit trail?
- does this avoid destructive edits to historical records?
- does this maintain tenant and branch isolation?
- does this keep privileged credentials off the frontend?
- does this avoid direct AI mutation of business data?
- does this include the smallest meaningful regression test?
- does this preserve restore and support workflows?

## Current Architectural Decision

The selected direction is:

```text
multi-client cloud architecture
local-first branch operation
shared cloud PostgreSQL by default
strict tenant isolation
PostgreSQL local and cloud database strategy
event/outbox sync
append-only inventory movements
ACID sale/refund/stock transactions
audited critical writes
AI for manager intelligence only
single-branch operations first
multi-branch workflows later
```

## Current Codebase Baseline

This section records the current implementation state observed before starting the hybrid cloud build-out.

### Current Backend Baseline

Current stack:

- FastAPI backend
- SQLAlchemy models
- Alembic migrations
- PostgreSQL production configuration
- JWT authentication
- role-based access using `admin`, `manager`, and `cashier`
- APScheduler background jobs
- local backup and diagnostics endpoints

Current backend strengths:

- local PostgreSQL is the production database target
- production config rejects unsupported database backends
- production config requires `SECRET_KEY`
- admin provisioning exists through `scripts/provision_admin.py`
- public self-registration is not exposed through the auth API
- product batches exist
- product batch expiry, quarantine status, and quantity exist
- sale creation uses row locks on products and sellable batches
- sale allocation uses FEFO across sellable batches
- expired and quarantined batches are excluded from sellable stock
- sale item records snapshot product name, dosage form, strength, batch number, expiry date, unit price, and total price
- money columns have been migrated to numeric types
- wholesale and retail sale pricing modes exist
- stock receipt flow exists and creates stock adjustment records
- manual stock adjustment flow exists and is manager-gated
- sale void/refund endpoints exist and restore stock
- end-of-day closeout endpoint exists
- audit service and activity log model exist
- critical product, user, sale, stock receipt, stock adjustment, batch update, void, and refund actions have audit logging started
- system diagnostics and backup status endpoints exist
- local backup and restore scripts exist for PostgreSQL

### Current Frontend Baseline

Current stack:

- React 18
- TypeScript
- Vite
- Zustand stores
- Axios API client
- TailwindCSS
- Recharts

Current frontend surfaces:

- login
- POS
- products
- sales
- stock adjustments
- suppliers
- notifications
- local settings/diagnostics
- admin dashboard

Current frontend strengths:

- authenticated route protection exists
- admin and admin/manager route guards exist
- POS is the default authenticated route
- POS search uses paginated product catalog API
- POS cart supports retail and wholesale pricing modes
- POS blocks out-of-stock additions client-side, with backend enforcement still authoritative
- dashboard data loads with `Promise.allSettled`, so one failed reporting request does not block all dashboard sections
- settings can surface backup and diagnostics information through system endpoints

### Current Testing Baseline

Existing tests cover parts of:

- auth and user workflows
- validation guards
- dashboard endpoints
- inventory workflows
- sale financial integrity
- operational controls
- frontend auth/cart/dashboard/settings behavior

Notable covered backend behaviors:

- username trimming on login
- manager cannot create manager users
- user update audit logging
- sale money rounding and numeric storage
- wholesale pricing
- today sales summary
- stock receipt creates batch, adjustment, and audit log
- FEFO sale depletion across batches
- void sale restores stock
- end-of-day closeout includes completed and refunded sales

### Current Operational Baseline

Current operational support includes:

- local PostgreSQL setup documentation
- Windows local deployment runbook
- backup and restore guide
- backup status file
- manual backup trigger endpoint
- local diagnostics endpoint
- Windows and Linux backup scripts
- Windows and Linux scheduled backup helpers
- go-live checklist
- missing operational controls checklist

The current go-live documentation correctly states that the system is not yet ready for unsupervised broad commercial rollout.

## Current Gap Summary

The current codebase is a strong local-first foundation, but it is not yet the hybrid cloud product described in this plan.

### Multi-Client And Cloud Gaps

Missing:

- `organization_id`
- `branch_id`
- `device_id`
- tenant model
- branch model
- device registration model
- cloud database schema
- cloud API
- cloud dashboard
- license/subscription model
- tenant isolation tests
- row-level security policies for any exposed cloud tables

### Sync Gaps

Missing:

- local sync outbox table
- sync event schema
- local sequence numbers
- idempotency keys
- sync worker
- cloud event ingestion API
- sync retry logic
- sync conflict records
- sync health dashboard
- device authentication for sync

### Inventory And Audit Gaps

Present but still incomplete:

- batch-aware sales and stock receipt exist
- stock adjustments exist
- audit logging exists

Still needed:

- formal inventory movement ledger as the authoritative movement history
- structured refund records separate from status changes
- structured void records separate from status changes
- stock take / physical count workflow
- price change history table
- receipt reprint tracking workflow
- controlled-drug register
- prescription enforcement workflow beyond product metadata
- audit logs committed inside the same transaction as every critical business write
- audit records with old/new value snapshots for more actions
- append-only protection for audit logs

### Role And Permission Gaps

Current roles are:

```text
admin
manager
cashier
```

Needed production roles:

```text
owner
branch_manager
pharmacist
cashier
inventory_clerk
auditor
support_technician
```

Needed permission model:

- granular permissions instead of only role hierarchy
- pharmacist approval permission
- controlled-drug dispensing permission
- stock adjustment permission
- refund/void approval permission
- backup/restore permission
- report/export permission
- support diagnostics permission

### Cash And Closeout Gaps

Started:

- end-of-day closeout summary exists

Still needed:

- cashier shift/session model
- opening cash
- payment method reconciliation
- cash drops
- counted cash
- expected cash
- variance
- closeout approval
- closeout audit record

### Backup And Recovery Gaps

Present:

- local backup scripts
- restore scripts
- backup status visibility
- backup documentation

Still needed:

- installer-driven scheduled backup verification
- restore drill evidence per client
- encrypted backup option
- offsite backup workflow
- cloud backup integration
- RPO/RTO tier documentation per client
- in-app stale backup warning

### Reporting And Dashboard Gaps

Present:

- local dashboard KPIs
- low stock report
- expiry report
- sales trend
- profit and revenue reports
- fast/slow moving product reports

Still needed:

- remove remaining mock growth values from release-facing dashboard views
- branch-aware reporting
- tenant-aware reporting
- cloud owner dashboard
- sync health reports
- backup health reports
- audit review reports
- controlled-drug reports
- refund/void anomaly reports

### AI Gaps

Present:

- rule-based operational insights service
- dead stock detection
- reorder quantity suggestion
- sales pattern analysis
- profit margin analysis

Still needed:

- real AI assistant service
- cloud dashboard AI chat interface
- approved AI tool registry
- prompt and tool safety boundaries
- AI audit logging
- human approval flow for AI-drafted actions
- protection against sending patient-identifiable data to AI
- source data references in AI answers

### Known Technical Risks To Track

Risks observed during orientation:

- several endpoints commit business data and then commit audit logs separately; critical write audit logs should eventually commit atomically with the business transaction
- user deletion is hard delete; production should prefer disable/deactivate for traceability unless a retention policy requires deletion
- refunds and voids are represented mainly through sale status plus stock restoration; production should add explicit reversal/refund records
- frontend route guards are useful but backend authorization remains the source of truth and must become more granular
- dashboard still contains mock growth percentages and must not present those as real business metrics
- tests use in-memory SQLite even though production targets PostgreSQL; critical transaction and locking tests should eventually run against PostgreSQL
- sale reversal fallback code references `timedelta` if a restored batch must be synthesized; this path should be reviewed before relying on it in production

## Immediate Build Order From Current State

The next implementation work should proceed in this order:

1. Create formal inventory movement ledger and move stock receipt, sale deduction, refund, void, and adjustment flows toward it.
2. Make audit logging atomic for critical write transactions.
3. Add explicit refund/void/reversal records instead of relying only on sale status.
4. Add stock take / physical count workflow.
5. Expand role model into granular permissions.
6. Add tenant, branch, and device tables locally and in planned cloud schema.
7. Add local sync outbox table and event-writing hooks inside critical transactions.
8. Build cloud ingestion API and idempotent event storage.
9. Build cloud owner dashboard around synced read models.
10. Add AI manager assistant on top of approved cloud reporting tools.

## Implementation Progress

This section must be updated as production hardening work lands.

### Completed Foundations

1. Inventory movement ledger

Status: implemented.

Implemented:

- append-only `inventory_movements` table
- inventory movement model and schema
- stock receipt movement records
- initial batch stock movement records
- sale deduction movement records
- sale reversal movement records
- stock adjustment movement records
- stock take correction movement records
- regression tests for movement creation

2. Atomic audit logging for critical writes

Status: implemented for current critical local write paths.

Implemented:

- sales write audit occurs before the same transaction commits
- sale reversal audit occurs before the same transaction commits
- product, batch, stock receipt, stock adjustment, user, category, and supplier audit writes moved into the same transaction as the business write
- regression test confirms sale, stock deduction, and movement ledger roll back when audit logging fails

3. Explicit sale reversal records

Status: implemented.

Implemented:

- `sale_reversals` table
- reversal type: void or refund
- reason
- reversed sale amount
- restored quantity
- performing user
- timestamp
- void/refund workflows create reversal records in the same transaction as stock restoration, movement ledger, sale status, and audit log
- regression tests for void/refund reversal records and duplicate reversal protection

4. Stock take / physical count workflow

Status: implemented for batch-level counts.

Implemented:

- `stock_takes` and `stock_take_items` tables
- create stock take draft from batch-level physical counts
- complete stock take with manager approval
- count completion creates stock correction adjustments
- count completion creates inventory movement records
- count completion is audit logged
- stale count protection blocks completion if batch quantity changed after count capture
- regression tests for correction application and stale count rejection

### Next Foundation

5. Granular permissions

Status: implemented for the first local hardening pass.

Goal:

- move beyond only `admin`, `manager`, and `cashier` role hierarchy
- introduce explicit permissions for sensitive operations
- keep current roles as presets initially to avoid disrupting existing users
- enforce permission checks server-side for critical workflows

Implemented:

- `can_refund_sale`
- `can_void_sale`
- `can_adjust_stock`
- `can_perform_stock_take`
- `can_manage_products`
- `can_manage_suppliers`
- `can_manage_categories`
- `can_manage_users`
- `can_view_reports`
- `can_trigger_backup`
- role-default permission fallback for existing users
- explicit per-user permission override list
- migration adding `users.permissions`
- regression tests for default permissions and explicit override behavior

Future permission targets:

- `can_override_price`
- `can_sell_prescription_only`
- `can_sell_controlled_drug`
- `can_override_batch`
- `can_export_data`
- `can_manage_devices`
- `can_manage_license`

6. Tenant / branch / device schema

Status: implemented as an expand-style foundation.

Implemented:

- `organizations` table
- `branches` table
- `devices` table
- branch codes unique per organization
- device status lifecycle
- nullable tenant references on current local business tables
- nullable `source_device_id` references on device-originated records
- schemas for organization, branch, and device records
- regression test proving tenant/branch/device records can link to business data

Current scope:

- schema foundation only
- existing single-branch local workflows still operate without requiring tenant IDs
- future work must backfill and enforce non-null tenant fields once provisioning and local installation identity exist

Next foundation:

7. Sync outbox

Status: implemented for local event recording.

Implemented:

- `sync_events` table
- `sync_event_counters` table for durable local sequence numbers
- event UUIDs for idempotency
- payload hashing using canonical JSON
- event status lifecycle: pending, sending, sent, failed
- retry and error fields for future sync worker
- outbox events written inside existing local transactions
- event recording for sales, reversals, stock receipt, stock adjustment, stock take, product changes, user changes, categories, and suppliers
- regression tests proving sync events are created on success
- regression test coverage that failed audit logging rolls back sale, stock, movement, and sync event writes

Current scope:

- local outbox only
- no cloud upload worker yet
- no cloud ingestion API yet
- no retry scheduler yet

Original goal:

- write sync events inside the same transaction as critical local business changes
- prepare local branch data for cloud upload without making POS dependent on internet

Next foundation:

8. Cloud ingestion API

Status: implemented for first-pass event acceptance and idempotency.

Implemented:

- `ingested_sync_events` table
- active registered device validation by `device_uid`
- organization/branch/device ownership checks
- idempotent event acceptance by `event_id`
- conflict rejection when the same `event_id` arrives with a different payload hash
- conflict rejection when the same device local sequence number arrives with a different event
- duplicate delivery tracking with `duplicate_count` and `last_duplicate_at`
- ingestion endpoint: `POST /sync/ingest`
- regression tests for first ingest, exact duplicate ingest, conflicting event hash, sequence conflict, and inactive device rejection

Current scope:

- cloud-side event storage only
- does not yet project ingested events into cloud reporting read models
- does not yet authenticate devices with signed credentials or rotating secrets
- does not yet include the local upload worker that sends pending outbox events

Original goal:

- accept events from registered branch devices
- validate event payloads
- store events idempotently using event IDs and local sequence numbers
- expose sync status without blocking local POS workflows

Next foundation:

9. Local sync upload worker

Status: implemented for local upload attempts.

Implemented:

- cloud sync configuration fields
- upload worker service for pending/failed local `sync_events`
- support for Supabase Edge Function or backend ingestion URL
- bearer token header support for server-side sync credentials
- scheduler job when cloud sync is enabled
- manual sync trigger endpoint: `POST /system/sync-now`
- sync health endpoint: `GET /system/sync-status`
- sync health fields in diagnostics
- retry/error tracking on local sync events
- regression tests for successful upload and missing identity failure

Current scope:

- worker uploads to configured ingestion API only
- no Supabase project credentials are hardcoded
- no frontend access to service-role credentials
- no cloud reporting projections yet

Original goal:

- read pending local `sync_events`
- submit them to the cloud ingestion endpoint
- mark events sent/failed without blocking POS
- retry safely with backoff
- expose sync health in local diagnostics

10. Cloud projection/read models

Status: implemented for first reporting facts.

Implemented:

- `cloud_sale_facts` table
- `cloud_inventory_movement_facts` table
- projection status fields on `ingested_sync_events`
- projector service for accepted Supabase/cloud events
- sale-created projection into cloud sales facts
- stock-received, stock-adjusted, stock-take-completed, and sale-reversed projection into inventory movement facts
- idempotent projection behavior
- projection status endpoint: `GET /sync/projection-status`
- manual projection endpoint: `POST /sync/project`
- admin-only access for projection status and manual projection controls
- regression tests for sale projection, inventory projection, idempotency, and projection status

Current scope:

- reporting facts only
- does not yet build richer branch inventory balance snapshots
- owner dashboard report endpoints are available as first-pass API contracts
- unsupported event types are marked projected/skipped to avoid blocking the queue

Next foundation:

11. Cloud reporting endpoints

Status: implemented for first owner-dashboard API contracts.

Implemented:

- `GET /cloud-reports/sales-summary`
- `GET /cloud-reports/branch-sales`
- `GET /cloud-reports/inventory-movements-summary`
- `GET /cloud-reports/sync-health`
- schemas for sales, branch sales, inventory movement, and sync health summaries
- organization and optional branch filters
- optional time-window filters for projected fact reports
- backend-enforced organization access for cloud report queries
- backend-enforced branch scoping for branch-assigned report users
- regression tests for organization/branch isolation and health counts
- regression tests for cross-organization denial, cross-branch denial, branch-limited reporting, and platform-admin access

Current scope:

- reporting endpoints query cloud projection tables only
- first cloud owner dashboard UI is available
- no AI assistant tools yet
- richer branch-role policy is still needed before real hosted exposure, including owner, multi-branch manager, auditor, and support technician semantics

Next foundation:

12. Cloud owner dashboard UI

Status: implemented for first reporting surface.

Implemented:

- query Supabase-backed projection tables by organization and branch
- expose sales summaries, inventory movement summaries, and sync health
- frontend cloud report API client methods
- dedicated `/cloud-dashboard` route
- sidebar navigation for admin and manager users
- organization and branch filters using backend tenant scope as the authority
- period filters for projected fact reports
- frontend regression test for dashboard data loading
- `/auth/me` now exposes user organization and branch assignment for scoped cloud queries

Current scope:

- dashboard reads the existing cloud report endpoints only
- projection status remains admin-only and is not shown to manager users in the first UI
- branch names are not yet hydrated from a branch registry endpoint, so the first UI labels branches by ID
- AI assistant backend endpoint is available, but no frontend chat UI yet

Next foundation:

13. AI manager assistant

Status: implemented for first backend assistant contract.

Implemented:

- `POST /ai-manager/chat`
- use the cloud reporting API surface as approved tool context
- answer manager questions about sales, inventory movement, sync health, and branch performance
- organization and branch access checks reused from cloud report authorization
- branch-assigned users are limited to their assigned branch even when no branch filter is sent
- deterministic read-only assistant response over approved cloud reporting facts
- do not allow AI to mutate stock, approve dispensing, override rules, or make clinical decisions
- explicit refusal for clinical, controlled-drug override, dispensing approval, and mutating requests
- regression tests for normal answers, branch scope, cross-branch denial, and unsafe-request refusal

Current scope:

- no frontend chat UI yet
- no external LLM provider is called by this first contract
- low-stock and expiry cloud report tools are still pending
- responses are deterministic summaries over approved reporting data, not free-form database access

Next foundation:

14. AI manager chat UI

- add a chat panel on the cloud dashboard or dedicated assistant route
- call `POST /ai-manager/chat`
- show data scope and safety notes with each answer
- include suggested prompts for sales, branch performance, inventory movement, and sync health
