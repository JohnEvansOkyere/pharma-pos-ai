# Database Architecture

## Database Engine

The production database engine is PostgreSQL.

SQLite is not supported by the current production settings. The settings validator requires `DATABASE_BACKEND=postgresql`, and `SECRET_KEY` must be set in production.

## Migration System

Alembic manages schema changes.

Current migration themes include:

- initial schema
- pharmaceutical product fields
- money columns converted to `Numeric`
- tenant/branch/device schema
- user permissions
- inventory movement ledger
- sync outbox
- sync ingestion
- cloud projection tables
- cloud stock snapshots
- AI weekly reports and delivery records
- AI provider settings
- sale pricing mode
- sale reversals
- stock takes
- batch-aware stock adjustments
- cloud reconciliation acknowledgements

Do not manually edit production database schemas. Add an Alembic migration for schema changes.

## Major Data Groups

Identity and security:

- `users`
- role and permission fields
- JWT issued by backend

Tenant topology:

- `organizations`
- `branches`
- `devices`

Catalog and inventory:

- `categories`
- `suppliers`
- `products`
- `product_batches`
- `inventory_movements`
- `stock_adjustments`
- `stock_takes`
- `stock_take_items`

Sales:

- `sales`
- `sale_items`
- `sale_reversals`

Operational:

- `notifications`
- `activity_logs`

Hybrid sync:

- `sync_event_counters`
- `sync_events`
- `ingested_sync_events`

Cloud reporting:

- `cloud_sale_facts`
- `cloud_inventory_movement_facts`
- `cloud_product_snapshots`
- `cloud_batch_snapshots`
- `cloud_reconciliation_acknowledgements`

AI manager:

- `ai_weekly_manager_reports`
- `ai_weekly_report_deliveries`
- `ai_weekly_report_delivery_settings`
- `ai_external_provider_settings`

## Numeric Money Handling

Money columns use `Numeric(12, 2)` in core sale, product, and reporting tables. Backend code uses Decimal helpers in critical pricing paths.

Do not use binary floats for committed money calculations. Frontend display can format numbers, but the backend owns authoritative price calculations.

## JSON Columns

JSON is used for:

- event payloads
- sync payload hashes and replay inputs
- AI report sections/tool results/safety notes
- provider/delivery metadata
- audit extra data
- user explicit permissions

For production query paths, avoid relying on deep JSON filtering unless indexed or moved to first-class columns.

## Indexing And Constraints

Important patterns already present:

- unique user username/email
- unique product SKU/barcode
- unique branch code per organization
- unique device UID
- unique local sync event id
- unique local sequence number
- unique cloud ingested event id
- unique cloud ingested device sequence
- unique cloud product snapshot per organization/branch/local product id
- unique cloud batch snapshot per organization/branch/local batch id
- unique AI weekly report per organization/scope/action week
- unique AI provider settings per organization
- unique cloud reconciliation acknowledgement per organization/issue key

As data volume grows, review indexes for:

- `organization_id`, `branch_id`, `created_at`
- sync status and retry queues
- cloud reporting date ranges
- audit log filters
- product search fields
