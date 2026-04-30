# API Surface Map

This map groups backend routes by operational responsibility. The backend remains the source of truth for permissions, validation, stock mutation, and audit logging.

## Authentication

Router: `/auth`

Purpose:

- login
- current user identity
- JWT authentication flow

Frontend users authenticate through the login page, then the API client attaches the bearer token to future requests.

## User Administration

Router: `/users`

Purpose:

- admin-controlled user management
- role and permission assignment
- user activation/deactivation workflows

Release rule: public self-registration must not exist in production builds.

## Product Catalog And Batches

Router: `/products`

Purpose:

- product list/search/catalog
- product create/update/deactivate
- batch create/update
- receive stock
- low-stock product listing

Production rule: product and batch changes must preserve inventory correctness and write sync events when they affect cloud reporting.

## Categories And Suppliers

Routers:

- `/categories`
- `/suppliers`

Purpose:

- master data for product organization and supplier tracking

These are important for inventory management but lower risk than sales and stock mutation.

## POS Sales

Router: `/sales`

Purpose:

- create sale
- list sales
- retrieve sale with items
- sale summary
- end-of-day closeout
- void sale
- refund sale

Production rule: sale creation and reversal are critical write paths. They must remain transaction-safe, batch-aware, and auditable.

## Stock Control

Routers:

- `/stock-adjustments`
- `/stock-takes`

Purpose:

- manual stock corrections
- damage/expiry write-offs
- returns to stock
- physical count drafts
- stock take completion

Production rule: stock mutation requires permission, reason, inventory movement records, and sync outbox events.

## Local Reporting And Alerts

Routers:

- `/dashboard`
- `/insights`
- `/notifications`

Purpose:

- local dashboard metrics
- rule-based operational insights
- expiry and low-stock notifications

These must not block POS operation if non-critical data is unavailable.

## Hybrid Sync And Cloud Projection

Router: `/sync`

Purpose:

- cloud ingestion of branch events
- projection status
- projection execution

Production rule: ingestion must be idempotent and projection failures must be observable.

## Cloud Reports And Reconciliation

Router: `/cloud-reports`

Purpose:

- cloud sales summary
- branch sales comparison
- cloud inventory movement summary
- sync health
- stock risk summary
- low-stock and expiry risk lists
- reconciliation summary
- issue acknowledgement/resolution
- admin-only reconciliation repair

Production rule: cloud reports are read models. Admin repairs affect cloud reporting state only and are audited.

## AI Manager

Router: `/ai-manager`

Purpose:

- AI manager chat
- weekly report generation/list/review
- weekly report delivery
- delivery history/settings
- external AI provider policy

Production rule: AI is read-only, scoped to approved reporting data, and must fall back safely when providers fail.

## System Operations

Router: `/system`

Purpose:

- backup status
- manual backup trigger
- diagnostics
- sync status and manual sync
- audit log listing
- audit log export

Production rule: operational endpoints require appropriate permissions, and admin audit review must stay tenant-scoped.
