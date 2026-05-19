# MEMORY.md — Codebase Source of Truth

> **Every agent session MUST read this file before starting work.**
> **Every agent session MUST update this file before closing work.**
>
> Update the [Change Log](#change-log) with: date, what changed, why, and which files were touched.

---

## 1. Project Identity

| Field              | Value                                                      |
| ------------------ | ---------------------------------------------------------- |
| **Name**           | Pharma POS AI                                              |
| **Type**           | Pharmaceutical Point-of-Sale system                        |
| **Deployment**     | On-site pharmacy installations (offline-first, local-only) |
| **Target**         | 5 pharmacy shops in Ghana                                  |
| **Stack**          | FastAPI + SQLAlchemy (backend), React + Vite (frontend), PostgreSQL |
| **Risk posture**   | Correctness and recoverability over feature count          |
| **Current phase**  | Audit follow-up and production hardening                   |
| **Go-live gate**   | `docs/GO_LIVE_CHECKLIST.md`                                |
| **Latest audit**   | `docs/audits/2026-05-15-production-readiness-audit-v2.md`  |

---

## 2. Architecture Overview

### 2.1 Backend (FastAPI + SQLAlchemy)

```
backend/
├── app/
│   ├── main.py                  # FastAPI app, lifespan, CORS, health check
│   ├── core/
│   │   ├── config.py            # Pydantic settings (env-driven)
│   │   ├── app_mode.py          # local_pos vs cloud_reporting route/write guards
│   │   ├── security.py          # JWT create/decode, bcrypt password hashing
│   │   └── money.py             # Decimal rounding helpers (round_money, to_decimal)
│   ├── db/
│   │   └── base.py              # SQLAlchemy engine, SessionLocal, Base, get_db
│   ├── models/                  # 17 SQLAlchemy model files, 25+ tables
│   │   ├── user.py              # User, UserRole, UserPermission, ROLE_DEFAULT_PERMISSIONS
│   │   ├── product.py           # Product, ProductBatch, PrescriptionStatus, DosageForm
│   │   ├── sale.py              # Sale, SaleItem, SaleReversal, SaleStatus, PaymentMethod
│   │   ├── activity_log.py      # ActivityLog (tamper-evident audit chain)
│   │   ├── inventory_movement.py # InventoryMovement (append-only ledger)
│   │   ├── sync_event.py        # SyncEvent, SyncEventCounter (outbox pattern)
│   │   ├── sync_ingestion.py    # IngestedSyncEvent (cloud ingestion)
│   │   ├── tenancy.py           # Organization, Branch, Device
│   │   ├── cloud_projection.py  # Cloud facts/snapshots incl. sale, stock, reconciliation, heartbeat
│   │   ├── ai_report.py         # AIWeeklyManagerReport, delivery settings
│   │   ├── stock_adjustment.py  # StockAdjustment, AdjustmentType
│   │   ├── stock_take.py        # StockTake, StockTakeItem
│   │   ├── restore_drill.py     # RestoreDrill (backup verification tracking)
│   │   ├── notification.py      # Notification, NotificationType
│   │   ├── category.py          # Category
│   │   └── supplier.py          # Supplier
│   ├── schemas/                 # 17 Pydantic schema files (request/response)
│   ├── api/
│   │   ├── __init__.py          # api_router with endpoint routers
│   │   ├── dependencies/        # Auth dependencies (get_current_user, require_*)
│   │   └── endpoints/           # Endpoint modules
│   │       ├── admin_tenancy.py # Vendor-admin client management + command center
│   │       ├── auth.py          # POST /auth/login, GET /auth/me
│   │       ├── users.py         # CRUD /users (admin-controlled)
│   │       ├── products.py      # CRUD /products, batches, receive-stock, low-stock
│   │       ├── sales.py         # POST /sales, void, refund, list, summary, closeout
│   │       ├── dashboard.py     # KPIs, trends, staff performance, revenue analysis
│   │       ├── stock_adjustments.py # Manual stock adjustments (damage, expiry, return)
│   │       ├── stock_takes.py   # Physical stock take workflow
│   │       ├── ai_manager.py    # AI chat, weekly reports, delivery, provider settings
│   │       ├── sync.py          # POST /sync/ingest, projection status
│   │       ├── cloud_reports.py # Cloud reporting read models
│   │       ├── notifications.py # Notification CRUD
│   │       ├── categories.py    # Category CRUD
│   │       ├── suppliers.py     # Supplier CRUD
│   │       ├── insights.py      # Dead stock, reorder suggestions, profit analysis
│   │       └── system_ops.py    # Backup, restore drills, diagnostics, audit logs, sync
│   └── services/                # 21 service modules
│       ├── audit_service.py     # Tamper-evident SHA-256 hash chain audit logging
│       ├── inventory_service.py # FEFO batch queries, stock recalculation, movement records
│       ├── sync_outbox_service.py # Monotonic sequence + payload hash outbox events
│       ├── sync_upload_service.py # Upload pending sync events to cloud API
│       ├── system_heartbeat_service.py # Enqueue local install health telemetry through sync outbox
│       ├── full_snapshot_sync_service.py # Enqueue one-time catalog/batch snapshots for cloud hydration
│       ├── cloud_projection_service.py # Project ingested events into reporting tables
│       ├── cloud_reconciliation_service.py # Cross-check local vs cloud data
│       ├── cloud_sales_trend_service.py # Cloud revenue comparison + branch anomaly detection
│       ├── cloud_stock_velocity_service.py # Cloud velocity + days-of-stock calculations
│       ├── cloud_dead_stock_service.py # Cloud dead-stock and slow-mover detection
│       ├── notification_service.py # Background expiry/low-stock/dead-stock alerts
│       ├── scheduler.py         # APScheduler background jobs
│       ├── ai_manager_service.py # Deterministic + LLM manager assistant
│       ├── ai_briefing_service.py # Ranked owner briefing findings from deterministic cloud evidence
│       ├── ai_finding_service.py # Persistent finding upsert/status workflow
│       ├── ai_llm_provider.py   # OpenAI/Claude/Groq HTTP adapters
│       ├── ai_provider_policy_service.py # Tenant-level AI provider policy
│       ├── ai_weekly_report_service.py # Weekly manager report generation
│       ├── ai_report_delivery_service.py # Email/Telegram delivery with retries
│       └── ai_insights.py       # Rule-based dead stock, reorder, sales patterns
├── alembic/                     # Database migrations (PostgreSQL)
│   └── env.py                   # Imports app.models so Alembic sees all mapped models
├── Dockerfile
├── requirements.txt
└── .env                         # ⚠️ NOT committed. Contains secrets, DB credentials
```

### 2.2 Frontend (React + Vite + TypeScript)

```
frontend/
├── src/
│   ├── App.tsx                  # Routes, ProtectedRoute, AdminRoute, AdminOrManagerRoute
│   ├── main.tsx                 # React root
│   ├── services/
│   │   └── api.ts               # Axios API client (singleton, auth interceptor)
│   ├── config/
│   │   └── appMode.ts           # frontend local_pos vs cloud_reporting route behavior
│   ├── stores/
│   │   ├── authStore.ts         # Zustand auth state (login, logout, loadUser)
│   │   ├── cartStore.ts         # Zustand POS cart (FEFO-aware, retail/wholesale)
│   │   └── themeStore.ts        # Dark/light theme
│   ├── pages/
│   │   ├── POSPage.tsx          # Primary workflow — the POS till
│   │   ├── ProductsPage.tsx     # Product management, batches, stock receipt
│   │   ├── SalesPage.tsx        # Sales history, void, refund
│   │   ├── DashboardPage.tsx    # Local dashboard (admin only)
│   │   ├── CloudDashboardPage.tsx # Cloud reporting dashboard
│   │   ├── AuditLogsPage.tsx    # Audit trail viewer
│   │   ├── StockAdjustmentsPage.tsx # Manual stock adjustments
│   │   ├── SettingsPage.tsx     # System settings, users, backup, AI config
│   │   ├── LoginPage.tsx        # Login form
│   │   ├── NotificationsPage.tsx # Notification center
│   │   ├── ClientsPage.tsx      # Vendor-admin command center + client provisioning
│   │   └── SuppliersPage.tsx    # Supplier management
│   ├── components/              # Reusable UI components
│   ├── hooks/                   # Custom React hooks
│   └── styles/                  # CSS
├── vite.config.ts               # Vite + VitePWA + dev proxy to :8000
├── Dockerfile
└── package.json
```

### 2.3 Infrastructure

```
docker-compose.yml               # PostgreSQL 15 + Backend + Frontend + pgAdmin (optional)
backup.bat / scripts/backup_postgres.sh   # Automated pg_dump scripts
restore.bat                      # Restore helper
install_backup_task.bat           # Windows scheduled task installer
scripts/install_backup_cron.sh   # Linux cron installer
start.bat / stop.bat             # Windows service helpers
setup-env.bat                    # First-time environment setup
installer.iss                    # Inno Setup installer script
deploy.sh                        # Render/Vercel deploy script
render.yaml                      # Render infrastructure config
```

---

## 3. Key Design Decisions

### 3.1 Why FEFO Batch-Based Dispensing
Pharmaceutical regulations require First-Expiry-First-Out dispensing. Every sale allocates stock from the batch with the nearest expiry date. The `_allocate_product_batches()` function in `sales.py` sorts by `expiry_date ASC, received_date ASC, id ASC` with `with_for_update()` row locking to prevent concurrent till race conditions.

### 3.2 Why Tamper-Evident Audit Chain
Pharmacy operations require provable audit trails. `AuditService` implements a SHA-256 hash chain where each entry's hash includes the previous entry's hash, creating a blockchain-like immutable record. Advisory locking (`pg_advisory_xact_lock`) prevents concurrent writes from breaking the chain. The `verify_integrity()` method can detect any tampering.

### 3.3 Why Sync Outbox Pattern (Not Direct API Calls)
Each pharmacy installation operates independently on a local database. The sync outbox (`SyncOutboxService`) records every mutation as a local event with a monotonic sequence number and payload hash. A background scheduler (`upload_sync_events`) periodically pushes pending events to the cloud ingestion API. This ensures no data loss if the internet is down.

### 3.4 Why Deterministic AI Fallback
The AI manager assistant (`AIManagerService`) always generates a deterministic answer from structured data first. The LLM (OpenAI/Claude/Groq) is optional and enhances the response. If the LLM is unavailable, the deterministic answer is returned. This ensures the AI feature works offline and never blocks operations.

### 3.5 Why Granular Permissions Over Role-Only
The `UserPermission` enum allows fine-grained control (e.g., a manager without void permissions, or a cashier with stock take access). `effective_permissions` falls back to `ROLE_DEFAULT_PERMISSIONS` for existing users who haven't been assigned explicit permissions, maintaining backward compatibility.

### 3.6 Why Local-First PostgreSQL
The system is designed to run entirely on a local PostgreSQL instance at each pharmacy. Docker Compose is the deployment mechanism. The cloud sync layer is additive — the system must work fully without it.

### 3.7 Why Append-Only Inventory Movements
Every stock change (sale, receipt, adjustment, return, correction, write-off) creates an `InventoryMovement` row with `quantity_delta`, `stock_after`, and source document linking. This creates a complete, queryable audit trail that can reconstruct stock levels at any point in time.

### 3.8 Why Multiple Pricing Modes
Pharmacies sell at both retail and wholesale prices. The `SalePricingMode` enum and cart store's `setPricingMode()` support switching between retail and wholesale within the same session. The backend validates that wholesale prices exist before allowing wholesale sales.

### 3.9 Why Restore Drills Are Tracked
A backup is worthless if nobody has verified it restores correctly. The `RestoreDrill` model and `system_ops.py` endpoints track when restore tests were performed, whether they passed, and which backup was tested. The `RestoreDrillStatus` includes a readiness checklist.

### 3.10 Why Cloud Projections Are Separate Tables
Cloud reporting uses separate "fact" and "snapshot" tables (`CloudSaleFact`, `CloudProductSnapshot`, etc.) instead of querying local tables. This isolates reporting from transactional workloads and allows the cloud to reconcile data independently.

### 3.11 Why Catalog Compliance Flags Are Non-Blocking In Current Ghana Deployments
The current client workflow treats `prescription_status`, `requires_id`, and `is_narcotic` as optional catalog metadata, not as POS checkout gates. Products may be sold without `has_prescription`, `prescription_number`, `customer_id_number`, or customer-name evidence solely because of those flags; this avoids imposing prescription-vs-normal-drug, ID-capture, or controlled-drug workflows the client does not use in daily operations.

### 3.12 Why Per-Device Sync Tokens Instead of a Shared Global Token
The original design compared the `Authorization` header against a single `CLOUD_SYNC_API_TOKEN` stored in the Render backend env — every client device used the same value. A compromised `.env` on one pharmacy machine would expose the sync endpoint for all clients, with no way to revoke just that device. The new model stores a `token_hash` (SHA-256 of the raw token) in the `Device` row. Each device gets a unique token at provisioning time. Disabling a rogue device is a single-row status update; no other clients are affected. The raw token is printed once by `provision_client.py` and never stored server-side.

### 3.13 Why Provisioning Runs From the Vendor's Machine, Not the Client's
`provision_client.py` connects directly to Supabase to create Organization, Branch, and Device rows — operations requiring admin DB credentials. Client machines should never hold those credentials; they communicate only through the Render backend API using their per-device token. The workflow: vendor runs the script locally before the site visit → gets a four-line env block → sends it to the technician → technician pastes it during `setup-env.bat`. No DB access is required on-site.

### 3.14 Why Vendor Admin Panel Is Separate From the Pharmacy Local Dashboard
The `/admin/*` API endpoints and `ClientsPage.tsx` are vendor-facing (John only, admin role). They live on Render/Vercel and manage the cloud-side tenancy records. The local pharmacy dashboard at `localhost:8080` is for pharmacy staff and has no concept of multi-tenancy. Keeping them separate means pharmacy admins cannot accidentally see or modify other clients' data, and the vendor panel does not depend on any individual pharmacy machine being online.

### 3.15 Why The Vendor Command Center Must Separate Reachability From Trust
The cloud side is downstream of the local-first pharmacy installs: local outbox events are uploaded to Render, then projected into cloud read models. A recent `Device.last_seen_at` only proves that a device contacted the cloud; it does not prove that the local database, scheduler, backups, or unsent outbox are healthy. Likewise, missing cloud sales can mean zero business, no connectivity, or delayed upload. The vendor dashboard therefore separates **device reachability**, **sync/data freshness**, **reconciliation state**, and now **heartbeat-projected local install health** so cloud views do not overstate trust.

### 3.16 Why Cloud Reporting Uses Business Time, Not Projection Time
Cloud reporting facts now distinguish the original local business timestamp from the cloud projection row timestamp. `SALE_CREATED` payloads include `occurred_at`, and `CloudSaleFact` plus sale-created `CloudInventoryMovementFact` rows store it. Business windows in cloud reports, the vendor command center, AI chat, and weekly AI reports use `coalesce(occurred_at, created_at)` so delayed sync does not move Monday sales into Wednesday revenue. `created_at` remains useful as projection/storage time and data freshness must still be judged from sync ingestion/projection metadata.

### 3.17 Why Existing Installs Need A Full Snapshot Sync
Cloud projection normally learns product and batch state from future local mutations. If sync is enabled after a pharmacy already has products, batches, and stock, early sale events can create placeholder cloud snapshots such as `Product 7` before the matching catalog events ever arrive. `POST /system/enqueue-cloud-snapshot` solves this by enqueueing current active products and their batches into the local outbox using the normal `PRODUCT_CREATED` and `PRODUCT_BATCH_CREATED` event shapes. It recalculates sellable stock first, preserves quarantined batch state, adds snapshot metadata, and records an audit log; upload still follows the normal local outbox path.

### 3.18 Why Stock Velocity Is Calculated From Sale Movement Facts
Cloud reorder urgency now uses `CloudInventoryMovementFact` rows created from `SALE_CREATED` events, not generic negative stock movement. This avoids treating stock adjustments, write-offs, stock takes, or corrections as customer demand. `GET /cloud-reports/stock-velocity` combines recent sold units with `CloudProductSnapshot.total_stock` to calculate average daily units sold, days of stock remaining, estimated stockout date, units needed, confidence, and urgency status. AI manager answers and the cloud dashboard use the same deterministic service so stock advice is grounded in auditable projected facts.

### 3.20 Why AI Findings Use a Fingerprint Instead of a Compound Null-Safe Unique Key
`ai_findings` tracks one active row per (org scope, branch scope, finding type). PostgreSQL 15 supports `NULLS NOT DISTINCT` on unique constraints, but SQLAlchemy does not expose that option portably. Instead each row has a `fingerprint = "<branch_id|0>:<type>"` string, and the unique constraint is on `(organization_id, fingerprint)`. This avoids NULL equality issues while keeping the upsert logic simple: a branch_id=None org-level finding produces fingerprint `"0:stock_out"`, and branch 5 produces `"5:stock_out"` — they are distinct rows with no collision. `AIFindingService.upsert_findings()` uses the fingerprint to look up and refresh existing open/snoozed rows without touching dismissed or resolved ones, preserving the owner's decision.

### 3.19 Why Revenue Trends Compare Equal Business-Time Windows
Cloud branch anomaly detection uses `CloudSaleFact.occurred_at` through the business-time reporting path, not projection time. `GET /cloud-reports/revenue-comparison` compares the requested current period with the immediately previous equal-length period, then classifies branch changes as `no_sales_current`, `severe_drop`, `drop`, `growth`, `new_sales`, or `stable`. This gives the dashboard and AI manager deterministic branch-drop evidence without asking an LLM to infer trends from raw rows. Operating-hours-aware no-sales alerts remain pending because they need branch opening-hours or expected-trading rules.

### 3.21 Why Installation Heartbeats Use The Sync Outbox
The cloud vendor dashboard must not treat `Device.last_seen_at` as proof that a pharmacy machine is locally healthy. `SYSTEM_HEARTBEAT` events are written to the local `sync_events` outbox first, then uploaded and projected like any other branch event. This keeps the design offline-safe: diagnostics are captured even while the internet is down, and the cloud later receives app version, database connectivity, scheduler state, outbox backlog, backup/restore status, disk capacity, uptime, and a deterministic readiness status in `CloudDeviceHeartbeatSnapshot`. The command center can now separate cloud reachability from local installation health, while true clock-skew comparison still needs a cloud-side drift rule.

### 3.22 Why AI Provider Selection Is Server-Side
External AI provider and model selection is a vendor/deployment concern, not a pharmacy customer workflow. The cloud dashboard no longer asks tenant admins to choose OpenAI/Claude/Groq or enter model names. `AIProviderPolicyService.resolve_provider()` now auto-selects an available server-side provider from configured API keys, honoring `AI_MANAGER_PROVIDER` when set to a usable provider and otherwise falling back to the first configured provider. `AIManagerLLMProvider` supplies provider-specific default models when `AI_MANAGER_MODEL` is blank. If no external API key is configured, the deterministic offline-safe assistant remains the fallback.

### 3.23 Why The Deployed Cloud App Has A Reporting-Only Mode
The same codebase can run locally at a pharmacy and in the cloud, but those deployments must not behave the same way. `APP_MODE=local_pos` keeps all POS/product/sales workflows available for the on-site installation. `APP_MODE=cloud_reporting` makes the backend reject unsafe local operational writes to POS, product, stock, notification, and system endpoints, while `VITE_APP_MODE=cloud_reporting` hides and redirects local operational pages in the browser. This prevents the deployed cloud portal from becoming a confusing second POS database with sales/products that differ from the synced local source of truth.

### 3.24 Why Five Specific KPIs Were Chosen For The CEO Dashboard
Revenue, stock counts, and risk flags already existed on the cloud dashboard. The five additional KPIs added in Phase 8.3 were chosen because each one changes a decision that cannot be correctly made from the existing data alone: (1) **Gross Profit** — revenue without margin is misleading for branch prioritisation and pricing; (2) **Total Stock Value** — managers need to know how much capital is locked in inventory before making purchasing decisions; (3) **Dead Stock Value (GHS)** — unit counts understate urgency; GHS value of idle stock makes the cost of inaction concrete; (4) **Average Transaction Value** — a falling basket average signals cashier, pricing, or stockout problems that require different responses from a falling sales count; (5) **Stockout Revenue Estimate** — converts a red "out of stock" badge into an estimated GHS loss figure, making the cost of delayed restocking explicit.

### 3.25 Why Cloud "Items Sold" Means Units Sold
The local dashboard's `total_items_sold` is `sum(SaleItem.quantity)`, not the number of sale lines. Cloud reporting now follows the same definition: `CloudSaleFact.item_count` stores the total units sold from the sale payload (`sum(item.quantity)`). This avoids a common mismatch where one sale line with quantity 11 looked like 1 item in cloud reporting but 11 items locally. New and reprojected facts use the corrected semantics automatically. Older already-projected cloud rows can be corrected through the audited admin reconciliation repair type `repair_sale_item_counts`, which recalculates `CloudSaleFact.item_count` from the accepted `SALE_CREATED` sync payload without mutating local POS data.

### 3.26 Why Data Health Is Separate From CEO KPIs
The cloud dashboard is for owner/CEO decision-making first. Business cards should answer revenue, margin, sales volume, basket size, stock value, and stock risk. Technical signals such as projection failures, duplicate deliveries, reconciliation issues, sync timestamps, and inventory movement row counts are still important, but they are grouped under a dedicated **Data Health** section so they explain whether the numbers can be trusted without competing with the business KPIs.

---

## 4. Critical Business Rules

1. **FEFO dispensing is mandatory** — stock must be dispensed from nearest-expiry batch first
2. **Sales are transaction-safe** — `with_for_update()` row locking on products and batches during sale creation
3. **Only COMPLETED sales should count in revenue** — `SaleStatus.COMPLETED` is the only valid state for financial reporting
4. **User provisioning is admin-controlled** — no public registration endpoint exists
5. **Catalog compliance flags are non-blocking in the current Ghana deployment** — `prescription_status`, `requires_id`, and `is_narcotic` remain available as metadata, but sale creation does not require prescription, customer-ID, or customer-name evidence solely because of those flags
6. **Voiding/refunding restores stock** — `_restore_sale_item_stock()` returns units to original or new batches
7. **Audit trail is immutable** — hash chain prevents silent record modification
8. **Sync events are idempotent** — duplicate event_id with same payload_hash is accepted, different hash is rejected

---

## 5. Known Issues & Technical Debt

> Cross-reference: `docs/audits/2026-05-15-production-readiness-audit-v2.md`

| ID     | Severity | Summary                                        | File(s)                    | Status      |
| ------ | -------- | ---------------------------------------------- | -------------------------- | ----------- |
| P1-01  | 🔴 Critical | User deletion cascades to sales + audit logs | `models/user.py:70-71`     | ✅ Fixed    |
| P1-02  | 🔴 Critical | Dashboard revenue includes voided/refunded   | `endpoints/dashboard.py`   | ✅ Fixed    |
| P1-03  | — | Prescription, customer-ID, and controlled-drug checkout gates intentionally removed for current client workflow; `prescription_status`, `requires_id`, and `is_narcotic` are metadata only | `endpoints/sales.py` | ✅ Superseded by product decision |
| P1-04  | — | Alembic metadata incomplete claim rejected in V2; importing `app.models` loads all models | `alembic/env.py`, `models/__init__.py` | ✅ Rejected |
| P1-05  | 🔴 Critical | Unsafe local deployment env can still use placeholder SECRET_KEY; startup validation is too weak | `core/config.py` | ✅ Fixed |
| P1-06  | 🔴 Critical | `/products/low-stock` route unreachable      | `endpoints/products.py`    | ✅ Fixed    |
| P1-07  | 🔴 Critical | No rate limiting on login                    | `endpoints/auth.py`        | ✅ Fixed    |
| P1-08  | 🔴 Critical | Backend accepts over-discounted sales that can produce negative totals | `endpoints/sales.py` | ✅ Fixed |
| P2-01  | 🟠 High    | Health check doesn't verify DB               | `main.py`                  | ✅ Fixed    |
| P2-02  | 🟠 High    | No connection pool limits                    | `db/base.py`               | ✅ Fixed    |
| P2-03  | 🟠 High    | PWA cache regex doesn't match API URLs       | `vite.config.ts`           | ✅ Fixed    |
| P2-04  | 🟠 High    | Cart validates against stale stock           | `stores/cartStore.ts`      | ⚠️ UX only — server validates correctly |
| P2-05  | 🟠 High    | AI insights ignores sale status              | `services/ai_insights.py`  | ✅ Fixed    |
| P2-06  | 🟠 High    | Notification service uses naive datetime     | `services/notification_service.py` | ✅ Fixed |
| P2-07  | 🟠 High    | Dashboard and operational insights lack server-side report permission checks | `endpoints/dashboard.py`, `endpoints/insights.py` | ✅ Fixed |
| P2-08  | 🟠 High    | Local core flows are not consistently tenant-scoped despite tenant-aware schema | Multiple files | ⚠️ Accepted (single-tenant per pharmacy by design) |
| P2-09  | 🟠 High    | Mandatory repository memory docs are ignored/untracked by git | `.gitignore` | ✅ Fixed |
| AI-P0-01 | 🔴 Critical | Cloud AI/reporting used projection time for sales, omitted sale movement facts, and sale payloads lacked reliable batch IDs | `sales.py`, `cloud_projection.py`, `cloud_projection_service.py`, cloud report/AI services | ✅ Fixed |
| AI-P0-02 | 🟠 High | No one-time full catalog/batch/current-stock snapshot sync for existing installs when cloud sync is enabled after data already exists | Sync/outbox tooling | ✅ Fixed |
| AI-P1-01 | 🟠 High | Cloud AI previously lacked persistent findings, recommendations, and briefing workflow | AI/cloud dashboard services | ✅ Fixed (persistent findings + decision workflow implemented) |
| AI-P1-02 | 🟠 High | Cloud AI/dashboard lacked product velocity and days-of-stock remaining despite having projected sale movement facts | `cloud_stock_velocity_service.py`, `cloud_reports.py`, `ai_manager_service.py`, cloud dashboard | ✅ Fixed |
| AI-P1-03 | 🟠 High | Cloud AI/dashboard lacked week-over-week revenue comparison and branch drop detection | `cloud_sales_trend_service.py`, `cloud_reports.py`, `ai_manager_service.py`, cloud dashboard | ✅ Fixed |
| AI-P1-04 | 🟠 High | Cloud AI/dashboard lacked dead-stock and slow-mover detection; weekly reports had no trust warning prefix; branch names missing from weekly report branch_sales | `cloud_dead_stock_service.py`, `cloud_reports.py`, `ai_manager_service.py`, `ai_weekly_report_service.py`, cloud dashboard | ✅ Fixed |
| OPS-P1-01 | 🟠 High | Vendor command center inferred install health from cloud contact only; no synced local heartbeat for DB, scheduler, outbox, backup, restore, disk, or uptime | `system_heartbeat_service.py`, `cloud_projection.py`, `admin_tenancy.py`, `ClientsPage.tsx` | ✅ Fixed / partial clock-skew follow-up |
| CLOUD-P1-01 | 🟠 High | Refund/void path needed recheck before adding cloud financial anomaly work | `sales.py`, `cloud_projection_service.py` | ✅ Rechecked — `SALE_REVERSED` already syncs and projects stock movement; dedicated financial reversal facts remain pending |
| CLOUD-P0-02 | 🔴 Critical | Deployed cloud app could look and behave like a separate POS against the cloud DB, creating cloud-only products/sales that confuse the synced reporting source of truth | `main.py`, `app_mode.py`, `App.tsx`, `Sidebar.tsx` | ✅ Fixed with explicit `local_pos` / `cloud_reporting` app modes |
| CLOUD-P0-03 | 🔴 Critical | Cloud "items sold" counted sale lines while local dashboard counted units sold, creating mismatched KPIs for the same synced sales | `cloud_projection_service.py`, `cloud_reconciliation_service.py`, `cloud_reports.py`, `CloudDashboardPage.tsx` | ✅ Fixed; existing projected rows can be repaired with `repair_sale_item_counts` |

---

## 6. Environment & Configuration

### Required Environment Variables (backend/.env)

| Variable                    | Purpose                              | Critical |
| --------------------------- | ------------------------------------ | -------- |
| `DATABASE_URL`              | PostgreSQL connection string — **do NOT set this in client .env files**. config.py builds it from POSTGRES_* vars. A hardcoded DATABASE_URL overrides POSTGRES_PASSWORD silently and causes authentication failures. | ⚠️ Leave unset |
| `SECRET_KEY`                | JWT signing key (min 32 chars)       | ✅       |
| `POSTGRES_DB/USER/PASSWORD` | Docker PostgreSQL setup              | ✅       |
| `APP_MODE`                  | `local_pos` for pharmacy installations; `cloud_reporting` for deployed reporting portal write guards | ✅       |
| `ENVIRONMENT`               | `production` or `development`        | ✅       |
| `ENABLE_BACKGROUND_SCHEDULER` | Enable APScheduler cron jobs       | ⚠️       |
| `CLOUD_SYNC_ENABLED`        | Enable sync upload to cloud          | Optional |
| `CLOUD_HEARTBEAT_INTERVAL_MINUTES` | Local installation telemetry enqueue interval when cloud sync is enabled | Optional |
| `AI_MANAGER_PROVIDER`       | `deterministic`, `openai`, `claude`, `groq` | Optional |
| `OPENAI_API_KEY`            | OpenAI API key (if AI enabled)       | Optional |
| `ANTHROPIC_API_KEY`         | Anthropic API key (if AI enabled)    | Optional |

### Database

- **Engine:** PostgreSQL 15 (Docker: `postgres:15-alpine`)
- **ORM:** SQLAlchemy 2.x with declarative Base
- **Migrations:** Alembic
- **Connection:** `SessionLocal` with `get_db()` dependency injection
- **Port:** 5432 (internal), 5435 (host-mapped in Docker)

### Ports

| Service   | Internal | External |
| --------- | -------- | -------- |
| PostgreSQL | 5432     | 5435     |
| Backend   | 8000     | 8000     |
| Frontend  | 80       | 8080     |
| pgAdmin   | 80       | 8081     |

---

## 7. Auth & Permissions Model

### Roles (hierarchical)
- `ADMIN` (level 3) — full access, all permissions by default
- `MANAGER` (level 2) — operational access, most permissions except admin-only
- `CASHIER` (level 1) — POS only, no default permissions

### Granular Permissions
`can_manage_products`, `can_manage_suppliers`, `can_manage_categories`, `can_manage_users`, `can_view_reports`, `can_void_sale`, `can_refund_sale`, `can_adjust_stock`, `can_perform_stock_take`, `can_trigger_backup`

### Auth Flow
1. `POST /api/auth/login` → returns JWT `access_token`
2. Frontend stores token in `localStorage`
3. Axios interceptor adds `Authorization: Bearer <token>` to all requests
4. Backend dependency `get_current_user()` decodes JWT, loads user from DB
5. Permission-specific dependencies (`require_void_sale`, etc.) check `effective_permissions`

---

## 8. Data Flow: Sale Creation

1. Cashier adds products to cart (frontend `cartStore`)
2. `POST /api/sales` with items, payment method, amounts
3. For each item:
   - Lock product row (`with_for_update()`)
   - Recalculate sellable stock from valid batches
   - Allocate from FEFO-sorted batches (`_allocate_product_batches`)
   - Validate unit price matches pricing mode
4. Create `Sale` with auto-generated invoice number (`INV-YYYYMMDD-NNNNNN`)
5. Create `SaleItem` rows with batch snapshots (batch_number, expiry_date)
6. Decrement batch quantities
7. Recalculate product `total_stock`
8. Record `InventoryMovement` (type: SALE_DISPENSED)
9. Record `SyncEvent` (type: SALE_CREATED) in outbox
10. Record `ActivityLog` via `AuditService` (hash-chained)
11. Commit transaction

---

## 9. Testing

### Backend Tests
- Location: `backend/tests/` (if present)
- Framework: pytest
- Run: `cd backend && pytest`

### Frontend Tests
- Location: `frontend/src/**/*.test.tsx`
- Framework: Vitest + jsdom
- Run: `cd frontend && npm test`
- Existing test files: `authStore.test.ts`, `cartStore.test.ts`, `LoginPage.test.tsx`, `DashboardPage.test.tsx`, `CloudDashboardPage.test.tsx`, `AuditLogsPage.test.tsx`, `SettingsPage.test.tsx`

---

## 10. Deployment

### Local Development
```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev  # port 3000, proxies /api to :8000
```

### Docker Production
```bash
docker compose up -d          # PostgreSQL + Backend + Frontend
docker compose --profile admin-tools up -d  # Include pgAdmin
```

### Deployment Modes

- Local pharmacy installs use `APP_MODE=local_pos` and `VITE_APP_MODE=local_pos`; POS, products, sales, stock, suppliers, notifications, and local settings remain available.
- Cloud deployments use `APP_MODE=cloud_reporting` and `VITE_APP_MODE=cloud_reporting`; frontend navigation is limited to cloud reporting/admin routes and backend unsafe local operational writes return `403`.

### Migrations
```bash
cd backend
alembic upgrade head          # Apply pending migrations
alembic revision --autogenerate -m "description"  # Generate migration
```

---

## Change Log

> **Format:** `YYYY-MM-DD HH:MM UTC | Agent/Person | What changed | Why | Files touched`

| Date | Who | What | Why | Files |
| ---- | --- | ---- | --- | ----- |
| 2026-05-19 18:25 UTC | Dex | Fixed Render blueprint start command to run migrations before serving | Live AI chat was returning 500 while browser reported CORS because real requests reached the backend but the cloud database likely lacked the new AI chat session tables. The live OPTIONS preflight returned the correct CORS header, confirming this was not a CORS allowlist issue. `render.yaml` now uses `bash scripts/render_start.sh`, which runs `python -m alembic upgrade head` before starting Uvicorn. | `render.yaml`, `MEMORY.md` |
| 2026-05-19 17:17 UTC | Dex | Added audited cloud sale item-count repair and fixed heartbeat DB probing | Existing cloud sale facts created before the units-sold correction could remain wrong even though new projections are fixed. Added `repair_sale_item_counts` so admins can recalculate projected `CloudSaleFact.item_count` values from accepted `SALE_CREATED` payloads, with audit logging and regression coverage. Also changed heartbeat telemetry to probe the active DB session so local health reflects the database the app is actually using. Verified with the full backend suite: 128 passed. | `backend/app/services/cloud_reconciliation_service.py`, `backend/app/services/system_heartbeat_service.py`, `backend/tests/test_cloud_reports.py`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-19 15:40 UTC | Dex | Regrouped cloud dashboard into business KPIs and a dedicated Data Health section | User clarified that CEO metrics should be clean decision-making KPIs and technical sync/reconciliation cards were noise. Removed Projection Failures, Reconciliation, and Net Stock Movement from the top KPI grid; added a Business Performance section for revenue, profit, sales count, units sold, average transaction, stock value, stock risk, expiry value risk, and stockout daily loss; added a Data Health section grouping trust state, sync freshness, projection counts, reconciliation status, and inventory movement details. Verified CloudDashboard tests and frontend production build. | `frontend/src/pages/CloudDashboardPage.tsx`, `frontend/src/pages/CloudDashboardPage.test.tsx`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-19 14:56 UTC | Dex | Rechecked Claude's CEO KPI work, fixed cloud item-count semantics, and added KPI trust badges | Claude had implemented the Phase 8.3 CEO KPI endpoints/cards, but cloud sales projection still counted item lines while the local dashboard counted units sold. Updated projection to store unit totals, made existing facts correct on re-projection, fixed the profit endpoint's event-type filter, added backend tests for profit/stock value/stockout impact and item-count semantics, completed Phase 8.2 trust badges on KPI cards, and fixed frontend mocks. Verified with 53 focused backend tests, CloudDashboard frontend tests, frontend production build, `py_compile`, and `git diff --check`. | `backend/app/services/cloud_projection_service.py`, `backend/app/api/endpoints/cloud_reports.py`, `backend/tests/test_cloud_projection_service.py`, `backend/tests/test_cloud_reports.py`, `frontend/src/pages/CloudDashboardPage.tsx`, `frontend/src/pages/CloudDashboardPage.test.tsx`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-19 14:30 UTC | Claude Sonnet 4.6 | Built all 5 CEO decision KPIs on the cloud dashboard (Phase 8.3) | Gross Profit card (`GET /cloud-reports/profit-summary`), Total Stock Value card (`GET /cloud-reports/stock-value`), Average Transaction Value (added to `CloudSalesSummary`), Dead Stock Value in GHS (added to `CloudDeadStockService` and table), Stockout Revenue Estimate card + table (`GET /cloud-reports/stockout-impact`). Frontend build clean, all backend modules compile. | `backend/app/schemas/cloud_reports.py`, `backend/app/api/endpoints/cloud_reports.py`, `backend/app/services/cloud_dead_stock_service.py`, `frontend/src/services/api.ts`, `frontend/src/pages/CloudDashboardPage.tsx`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-19 14:00 UTC | Claude Sonnet 4.6 | Identified and documented 5 missing CEO KPIs that affect decision-making (Phase 8.3) | Gross Profit, Total Stock Value, Dead Stock Value in GHS, Average Transaction Value, and Stockout Revenue Estimate were each validated against available cloud projection data before being added to the checklist. Each changes a decision that cannot be correctly made from existing data alone. | `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-19 13:00 UTC | Claude Sonnet 4.6 | Added AI chat conversation memory and role gate (Phase 7.4 P3) | Manager said AI chat must remember the conversation within a session, support "New Chat" to start fresh, show past sessions in a history list, and be restricted to manager/admin roles only (not cashier/sales staff). Added `AIChatSession` and `AIChatMessage` models, Alembic migration `m3b4c5d6e7f8`, `GET /ai-manager/sessions`, `GET /ai-manager/sessions/{id}/messages` endpoints, session-aware `POST /ai-manager/chat` (auto-creates session, loads last 20 messages as LLM context, persists messages). LLM provider now passes conversation history in messages array for OpenAI/Groq/Claude. Chat endpoint role-gated to `require_manager` (CASHIER excluded). Frontend adds session state, session history panel, "New Chat" button, and hides the chat card from non-manager users. 121 backend tests pass, frontend builds clean. | `backend/app/models/ai_report.py`, `backend/app/models/__init__.py`, `backend/alembic/versions/m3b4c5d6e7f8_add_ai_chat_sessions.py`, `backend/app/schemas/ai_manager.py`, `backend/app/services/ai_llm_provider.py`, `backend/app/services/ai_manager_service.py`, `backend/app/api/endpoints/ai_manager.py`, `backend/tests/test_ai_manager.py`, `frontend/src/services/api.ts`, `frontend/src/pages/CloudDashboardPage.tsx`, `MEMORY.md` |
| 2026-05-19 11:33 UTC | Dex | Added explicit local POS vs cloud reporting deployment modes | The cloud deployment was exposing local POS/product/sales workflows backed by the cloud DB, which could confuse users and create cloud-only operational data separate from local sync projections. Added backend `APP_MODE` validation, a cloud-reporting unsafe-write guard, frontend `VITE_APP_MODE` routing/sidebar cleanup, cloud/default login routing, deployment docs/env defaults, Phase 8 checklist items, and regression coverage for the write guard. Verified with `python3 -m pytest backend/tests/test_app_mode.py`, `python3 -m py_compile backend/app/core/app_mode.py backend/app/core/config.py backend/app/main.py`, `npm run build`, and `git diff --check`. | `backend/app/core/app_mode.py`, `backend/app/core/config.py`, `backend/app/main.py`, `backend/tests/test_app_mode.py`, `backend/.env.example`, `backend/.env.client.example`, `docker-compose.yml`, `frontend/Dockerfile`, `frontend/src/config/appMode.ts`, `frontend/src/App.tsx`, `frontend/src/components/layout/Sidebar.tsx`, `frontend/src/pages/LoginPage.tsx`, `frontend/src/vite-env.d.ts`, `render.yaml`, `docs/operations/render-vercel-deployment.md`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-19 10:37 UTC | Dex | Fully removed frontend AI provider policy UI and API client code | User requested the customer-facing model/provider configuration be cleaned out, not merely hidden. Removed unused dashboard types, state, load/save handlers, panel component, API client methods, and test mocks/assertions. Backend compatibility endpoints remain, but the frontend no longer exposes or calls them. Verified focused CloudDashboard tests and frontend production build. | `frontend/src/pages/CloudDashboardPage.tsx`, `frontend/src/pages/CloudDashboardPage.test.tsx`, `frontend/src/services/api.ts`, `MEMORY.md` |
| 2026-05-19 10:30 UTC | Dex | Removed customer-facing AI model/provider configuration and made provider resolution server-side | Pharmacy customers should not need to understand provider/model choices. External AI now works from server-side API key configuration with provider-specific default models, while the dashboard no longer renders or loads the External AI Policy panel. Deterministic AI remains the fallback when no API key is configured. Verified focused AI manager tests, focused CloudDashboard tests, and frontend production build. | `backend/app/services/ai_llm_provider.py`, `backend/app/services/ai_provider_policy_service.py`, `backend/.env.example`, `backend/tests/test_ai_manager.py`, `frontend/src/pages/CloudDashboardPage.tsx`, `frontend/src/pages/CloudDashboardPage.test.tsx`, `MEMORY.md` |
| 2026-05-19 09:50 UTC | Dex | Added synced local installation heartbeat telemetry and command-center readiness | The next cloud command-center gap was distinguishing a device that merely contacted the cloud from a pharmacy machine that is locally healthy. Added `SYSTEM_HEARTBEAT` outbox events, heartbeat payload builder, scheduler job, manual enqueue endpoint, cloud heartbeat snapshot projection, command-center readiness counts/attention items, Clients page install-health display, checklist corrections, and regression tests. Rechecked refund/void: `SALE_REVERSED` already syncs and projects stock restoration; dedicated financial reversal facts remain future work. Verified with 122 backend tests passing and a frontend production build. | `backend/app/core/config.py`, `backend/app/models/sync_event.py`, `backend/app/models/cloud_projection.py`, `backend/app/models/__init__.py`, `backend/alembic/versions/l2a3b4c5d6e7_add_cloud_device_heartbeat_snapshots.py`, `backend/app/services/system_heartbeat_service.py`, `backend/app/services/scheduler.py`, `backend/app/services/cloud_projection_service.py`, `backend/app/api/endpoints/system_ops.py`, `backend/app/api/endpoints/admin_tenancy.py`, `backend/app/schemas/system.py`, `backend/app/schemas/tenancy.py`, `backend/.env.example`, `backend/.env.client.example`, `backend/tests/test_system_heartbeat_service.py`, `backend/tests/test_cloud_projection_service.py`, `backend/tests/test_admin_command_center.py`, `frontend/src/pages/ClientsPage.tsx`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-19 03:10 UTC | Claude Sonnet 4.6 | Implemented persistent AI findings workbench (Phase 7.3 P2) | Owner briefing was ephemeral; CEO needs to save, track, acknowledge, snooze, dismiss, and resolve findings across sessions. Added AIFinding model + migration, AIFindingService with fingerprint-based upsert (no-duplicate, no-clobber-dismissed), GET /ai-manager/findings, PATCH /ai-manager/findings/{id}, persist=true param on briefing endpoint, Saved Findings panel with action buttons in CloudDashboardPage. 3 new finding tests; 119 backend tests pass. | `backend/app/models/ai_report.py`, `backend/app/models/__init__.py`, `backend/alembic/versions/k1f2a3b4c5d6_add_ai_findings.py`, `backend/app/services/ai_finding_service.py`, `backend/app/schemas/ai_manager.py`, `backend/app/api/endpoints/ai_manager.py`, `frontend/src/services/api.ts`, `frontend/src/pages/CloudDashboardPage.tsx`, `backend/tests/test_ai_manager.py`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-19 UTC | Claude Sonnet 4.6 | Completed P0 trust gates + P1 dead-stock detection + P3 branch names | Weekly report executive summary now prepends DATA TRUST WARNING when sync/reconciliation is degraded. Added `GET /cloud-reports/dead-stock` (dead stock = zero sales; slow mover = <0.3 units/day). Integrated into AI manager tool_results and compose_answer. Added Dead Stock & Slow Movers card to cloud dashboard. Added branch names to weekly report branch_sales. Updated AI manager branch response to use branch name. 113 backend tests pass. | `backend/app/services/cloud_dead_stock_service.py` (new), `backend/app/services/ai_weekly_report_service.py`, `backend/app/services/ai_manager_service.py`, `backend/app/api/endpoints/cloud_reports.py`, `backend/app/schemas/cloud_reports.py`, `frontend/src/services/api.ts`, `frontend/src/pages/CloudDashboardPage.tsx`, `backend/tests/test_cloud_reports.py`, `backend/tests/test_ai_manager.py`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-19 02:10 UTC | Dex | Added cloud revenue comparison and branch trend anomaly detection | The next AI/dashboard hardening step was equal-window revenue comparison and branch drop detection. Added `GET /cloud-reports/revenue-comparison`, deterministic sales trend service, AI manager trend answers/tool data, cloud dashboard Branch Trend list, checklist updates, and regression tests. Verified backend AI/cloud report tests and the focused CloudDashboard frontend test. | `backend/app/api/endpoints/cloud_reports.py`, `backend/app/schemas/cloud_reports.py`, `backend/app/services/cloud_sales_trend_service.py`, `backend/app/services/ai_manager_service.py`, `backend/tests/test_cloud_reports.py`, `backend/tests/test_ai_manager.py`, `frontend/src/services/api.ts`, `frontend/src/pages/CloudDashboardPage.tsx`, `frontend/src/pages/CloudDashboardPage.test.tsx`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-19 02:02 UTC | Dex | Added cloud stock velocity and days-of-stock reporting | The next AI/dashboard hardening step was to turn sale-created movement facts into actionable reorder urgency. Added `GET /cloud-reports/stock-velocity`, deterministic velocity service, AI manager tool integration, cloud dashboard Stock Velocity list, checklist updates, and regression tests. Verified backend AI/cloud report tests and the focused CloudDashboard frontend test. | `backend/app/api/endpoints/cloud_reports.py`, `backend/app/schemas/cloud_reports.py`, `backend/app/services/cloud_stock_velocity_service.py`, `backend/app/services/ai_manager_service.py`, `backend/tests/test_cloud_reports.py`, `backend/tests/test_ai_manager.py`, `frontend/src/services/api.ts`, `frontend/src/pages/CloudDashboardPage.tsx`, `frontend/src/pages/CloudDashboardPage.test.tsx`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-19 01:52 UTC | Dex | Added one-time full catalog/batch snapshot enqueue for cloud sync | Existing pharmacy installs can have products and batches before cloud sync is enabled, causing cloud projections and AI dashboards to start with placeholder/incomplete catalog state. Added `POST /system/enqueue-cloud-snapshot`, a snapshot enqueue service, audit logging, checklist update, and regression tests. Verified with 59 related backend tests passing. | `backend/app/api/endpoints/system_ops.py`, `backend/app/schemas/system.py`, `backend/app/services/full_snapshot_sync_service.py`, `backend/tests/test_full_snapshot_sync_service.py`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-19 01:47 UTC | Dex | Continued Claude's stopped cloud AI dashboard checklist/P0 hardening work | The two final AI audit reports agreed that cloud facts needed correction before trustworthy CEO-style advice. Added sale `occurred_at`, reliable sale item `batch_id`, sale-created movement facts, business-time report windows, an AI chat trust warning, Phase 7 checklist items, and regression tests. Verified with 55 related backend tests passing. | `backend/app/api/endpoints/sales.py`, `backend/app/api/endpoints/cloud_reports.py`, `backend/app/api/endpoints/admin_tenancy.py`, `backend/app/models/cloud_projection.py`, `backend/app/services/cloud_projection_service.py`, `backend/app/services/ai_manager_service.py`, `backend/app/services/ai_weekly_report_service.py`, `backend/alembic/versions/j0e1f2a3b4c5_add_occurred_at_to_cloud_sale_facts.py`, `backend/tests/test_cloud_projection_service.py`, `backend/tests/test_cloud_reports.py`, `backend/tests/test_sales_financial_integrity.py`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-19 01:02 UTC | Dex | Added code-confirmed cloud AI dashboard audit document | User provided Claude's report and asked to verify which claims align with the code. The new doc confirms the main conclusion, corrects overstated claims about weekly reports, branch names, and inventory movement projection, and records the recommended P0-P3 AI/dashboard roadmap. | `docs/ai/2026-05-19-cloud-ai-dashboard-audit.md`, `docs/ai/README.md`, `MEMORY.md` |
| 2026-05-19 00:54 UTC | Dex | Audited cloud dashboard and AI manager architecture after cloud sync started working | Current AI is read-only and grounded in cloud projections, weekly reports, sync health, stock risk, and reconciliation, but it is still a narrow chat/report summarizer. To become a CEO-grade advisor it needs a durable intelligence/workbench layer with ranked findings, evidence, freshness/trust gates, decision workflow, anomalies, product velocity, margin, refunds/voids, heartbeat telemetry, and follow-up tracking. | `MEMORY.md` |
| 2026-05-19 00:20 UTC | Dex | Narrowed sync failure to cloud device registration mismatch | User-provided client laptop diagnostics showed the local backend now has `CLOUD_SYNC_ENABLED=True`, correct ingest URL, token present, device UID `7b764ab9-1e89-4239-b55a-eb2602033e82`, org `3`, branch `2`, and scheduler registered `Upload sync events`. Local `sync_events` are failing with `HTTP 403 {"detail":"Device is not registered"}`. This means the Render `/api/sync/ingest` database does not have a `devices.device_uid` row matching the submitted UID, or the vendor dashboard and ingest URL are pointed at different backend/database environments. Events at retry_count 10 will not retry automatically until reset/requeued after registration is corrected. | `MEMORY.md` |
| 2026-05-19 00:10 UTC | Dex | Diagnosed local-to-cloud sync failure | Running backend container was healthy at the Docker level but `/health` returned DB disconnected because `backend/.env` still sets `DATABASE_URL` to host-style `localhost:5435`; inside Docker that overrides `POSTGRES_HOST=db` and points back into the backend container. Effective container sync settings also showed `CLOUD_SYNC_ENABLED=false` and no ingest URL/token/device/org/branch values. Local outbox had pending `sale_created` events, but upload cannot run until DB connectivity and cloud sync env are corrected. Render cloud `/health` was healthy. | `MEMORY.md` |
| 2026-05-18 21:37 UTC | Dex | Implemented admin-only client command center P0 layer | User clarified the dashboard is only visible to the admin and wanted the vendor home to show real operational intelligence. Added `/admin/command-center` guarded by `require_vendor_admin`, aggregating tenancy, sync ingestion, projected sales, product snapshots, and batch snapshots into fleet coverage, data trust, money pulse, stock risk, attention queue, and organization summaries. Upgraded `/clients` UI into an admin-only command center and updated the go-live checklist to mark completed/partial dashboard insight work. | `backend/app/api/endpoints/admin_tenancy.py`, `backend/app/schemas/tenancy.py`, `frontend/src/services/api.ts`, `frontend/src/pages/ClientsPage.tsx`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-18 21:26 UTC | Dex | Expanded the go-live checklist into a vendor command-center insight roadmap | User wanted the client management dashboard to feel like an owner’s operational home, not a minimal demo. Added local-first/cloud-projection guardrails, marked the implemented provisioning baseline, and listed P0/P1/P2 insights for fleet health, sync freshness, reconciliation, sales, stock risk, telemetry, support, security, and portfolio intelligence. Added a MEMORY design decision separating device reachability from data trust. | `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-18 UTC | Claude Sonnet 4.6 | **Cloud vendor admin dashboard — client provisioning UI + admin tenancy API** | Vendor (John) had no way to create pharmacy client records (org/branch/device) or generate per-device tokens without running a Python script with DB credentials. Built `/admin/*` REST API (admin-only) for full CRUD on organizations, branches, and devices with on-demand token generation/rotation. Built `ClientsPage.tsx` with stats bar, expandable org→device tree, 3-step provisioning wizard (shows env block once), enable/disable toggle, and token rotation dialog. Added `/clients` route (admin-only) and "Clients" sidebar nav item. Removed `CLOUD_SYNC_REQUIRE_TOKEN` from `.env.client.example` (server-side setting, not for client machines). | `backend/app/api/endpoints/admin_tenancy.py`, `backend/app/schemas/tenancy.py`, `backend/app/api/__init__.py`, `frontend/src/pages/ClientsPage.tsx`, `frontend/src/App.tsx`, `frontend/src/components/layout/Sidebar.tsx`, `backend/.env.client.example`, `docs/GO_LIVE_CHECKLIST.md` |
| 2026-05-18 UTC | Claude Sonnet 4.6 | **Fix sync token tests broken by per-device token_hash migration** | `registered_device` fixture created devices without `token_hash`; new `_authenticate_device` always rejected them. Split None-hash (503 misconfiguration) from bad-hash (401 invalid). | `backend/app/api/endpoints/sync.py`, `backend/tests/test_sync_ingestion.py` |
| 2026-05-18 19:24 UTC | Dex | Identified likely live CORS mismatch from Vercel deployment screenshot | Screenshot showed both the stable alias `https://pharma-pos-ai.vercel.app` and a deployment-specific URL `https://pharma-pos-enz81525u-john-evans-okyeres-projects.vercel.app`; opening the deployment URL would produce a different browser origin than the one currently allowlisted in Render | `MEMORY.md` |
| 2026-05-18 19:21 UTC | Dex | Verified live Render CORS behavior for the production Vercel origin | A live `OPTIONS` request and an actual failed `POST /api/auth/login` from origin `https://pharma-pos-ai.vercel.app` both returned `Access-Control-Allow-Origin: https://pharma-pos-ai.vercel.app`; if the browser still reports missing CORS headers, the active page origin is likely different, stale, or the screenshot came from before the config took effect | `MEMORY.md` |
| 2026-05-18 19:18 UTC | Dex | Investigated deployed login failure and traced it to Render CORS allowlist configuration | Browser reports showed the backend returned `200` for `/api/auth/login` but omitted `Access-Control-Allow-Origin`; repo config confirms Render requires `BACKEND_CORS_ORIGINS` to be set explicitly for the deployed frontend origin, otherwise it falls back to localhost only | `MEMORY.md` |
| 2026-05-18 UTC | Claude Sonnet 4.6 | **Per-device sync auth — token_hash on Device, provision_client.py script** | Single shared `CLOUD_SYNC_API_TOKEN` on Render meant all clients shared one secret with no per-device revocation. Replaced with per-device SHA-256 token hash stored on the Device row. `provision_client.py` now creates Org + Branch + Device + token in Supabase from vendor's machine and prints the env block to paste into the client installer. Sync endpoint's `_require_sync_token`+`_get_active_device` merged into `_authenticate_device` which also updates `last_seen_at`. | `backend/app/models/tenancy.py`, `backend/alembic/versions/i9d0e1f2a3b4_add_device_token_hash.py`, `backend/app/api/endpoints/sync.py`, `backend/scripts/provision_client.py` |
| 2026-05-18 UTC | Claude Sonnet 4.6 | **Cloud sync env block added to .env.client.example** | Client installers had no guidance on cloud sync configuration fields. Added commented CLOUD_SYNC_* and CLOUD_PROJECTION_* section with all required variables, disabled by default. | `backend/.env.client.example` |
| 2026-05-18 UTC | Claude Sonnet 4.6 | **Render free tier deployment fixes — migrations in background task, CORS as plain string** | Two Render issues: (1) alembic running in lifespan blocked port binding — uvicorn only binds after lifespan completes, so health check timed out; fixed by firing migrations as `asyncio.create_task` background thread. (2) `BACKEND_CORS_ORIGINS` typed as `List[str]` caused pydantic-settings to call `json.loads()` at source level, crashing on plain URL and empty string; fixed by storing as `str` with a `cors_origins` property. `env_ignore_empty=True` added to SettingsConfigDict. Render start script simplified to pure uvicorn. | `backend/app/main.py`, `backend/app/core/config.py`, `backend/scripts/render_start.sh` |
| 2026-05-17 UTC | Dex | Removed the remaining controlled-drug checkout gate | User requested no drug-class checkout restrictions in the current POS workflow | `backend/app/api/endpoints/sales.py`, `backend/tests/test_inventory_workflows.py`, `MEMORY.md` |
| 2026-05-17 UTC | Dex | Removed the customer-ID checkout gate and cleared seeded Artemether ID requirement | Current client workflow does not capture customer IDs at POS, and Artemether’s seeded `requires_id=True` created unwanted friction | `backend/app/api/endpoints/sales.py`, `backend/tests/test_inventory_workflows.py`, `scripts/seed_data.py`, `backend/scripts/seed_data.py`, `MEMORY.md` |
| 2026-05-17 UTC | Dex | Removed the prescription-status checkout gate and documented the new non-blocking policy | Current Ghana client workflow does not distinguish prescription vs normal drugs at POS, so that metadata must not stop sales | `backend/app/api/endpoints/sales.py`, `backend/tests/test_inventory_workflows.py`, `MEMORY.md` |
| 2026-05-17 UTC | Claude Sonnet 4.6 | **UI redesign — sidebar, typography, layout, dashboard** | Client demo feedback: sidebar too wide, fonts too large, dashboard too boring. Sidebar rebuilt as always-navy `#1e3050`, narrowed from w-64→w-52, header/padding reduced, base font dropped from 17px→13px, system font stack, duplicate KPI row removed, "Today at a glance" inline strip added, chart heights reduced. `DESIGN.md` created as design system reference. `backend/scripts/seed_data.py` added (copy from root scripts/ so Docker image includes it). Desktop shortcut step added to Windows Runbook. | `frontend/src/styles/index.css`, `frontend/src/components/layout/Sidebar.tsx`, `frontend/src/components/layout/Header.tsx`, `frontend/src/components/layout/MainLayout.tsx`, `frontend/src/pages/DashboardPage.tsx`, `docs/DESIGN.md`, `docs/WINDOWS_LOCAL_DEPLOYMENT_RUNBOOK.md`, `backend/scripts/seed_data.py` |
| 2026-05-17 UTC | Claude Sonnet 4.6 | **First client pharmacy installation — hardening and troubleshooting** | Live install exposed four bugs: (1) `install_backup_task.bat` SCHTASKS `/D` flag leaking from `cd /d` in `/TR` string; (2) `POSTGRES_PASSWORD` with `@` broke SQLAlchemy URL parsing — fixed with `quote_plus`; (3) hardcoded `DATABASE_URL` in `.env` overrides `POSTGRES_PASSWORD` silently; (4) Alembic configparser chokes on `%`-encoded chars in URL. Runbook updated with Troubleshooting section, password restrictions, DATABASE_URL warning. `alembic/env.py` patched to escape `%%`. Also created `backend/.env.client.example` (minimal client template), fixed username typo in `docker-compose.client.yml` (`johnevansokeyere` → `johnevansokyere`), and updated `setup-env.bat` to prefer `.env.client.example`. | `docs/WINDOWS_LOCAL_DEPLOYMENT_RUNBOOK.md`, `backend/alembic/env.py`, `backend/app/core/config.py`, `backend/.env.client.example`, `setup-env.bat`, `install_backup_task.bat`, `docker-compose.client.yml` |
| 2026-05-16 UTC | Claude Sonnet 4.6 | **Docs updated to reflect registry-based client deployment** | README and Windows runbook had stale commands (wrong compose file, wrong provision_admin path, no PostgreSQL test instructions). All references updated to match actual deploy model. | `README.md`, `docs/WINDOWS_LOCAL_DEPLOYMENT_RUNBOOK.md` |
| 2026-05-16 UTC | Claude Sonnet 4.6 | **Backend tests now run against PostgreSQL in CI** | Tests were using SQLite in-memory which silently skipped PostgreSQL-specific code (pg_advisory_xact_lock, ENUMs). conftest.py now reads TEST_DATABASE_URL and uses TRUNCATE between tests for isolation. CI workflow spins up postgres:15-alpine service container. | `backend/tests/conftest.py`, `.github/workflows/build.yml` |
| 2026-05-16 UTC | Claude Sonnet 4.6 | **GitHub Container Registry CI/CD pipeline + client deployment package** | Moving from build-from-source to pre-built images on ghcr.io. Clients only need 5 files — no source code on their machine. Push to main → images auto-build via GitHub Actions. | `.github/workflows/build.yml`, `docker-compose.client.yml`, `backend/scripts/provision_admin.py`, `backend/Dockerfile`, `provision-admin.bat` |
| 2026-05-16 UTC | Claude Sonnet 4.6 | **Windows install runbook rewritten for Docker Compose path; backup.bat fixed for Docker** | First client installation today — runbook lacked actual Docker Compose commands, admin provisioning step for Docker, and backup.bat failed against Docker port 5435. Runbook now covers WSL2, Docker Desktop, `docker compose up -d`, `docker exec alembic upgrade head`, `docker exec provision_admin.py`, and Windows Firewall. backup.bat now auto-detects Docker container and uses `docker exec pg_dump` instead of requiring native pg_dump on the host. | `docs/WINDOWS_LOCAL_DEPLOYMENT_RUNBOOK.md`, `backup.bat`, `docs/GO_LIVE_CHECKLIST.md` |
| 2026-05-15 20:15 UTC | Antigravity | **Production readiness remediation — all critical code defects resolved** | Fix all verified P0/P1/P2 findings from both audits. Independently re-verified every claim before fixing. | `models/user.py`, `endpoints/users.py`, `endpoints/dashboard.py`, `endpoints/sales.py`, `endpoints/products.py`, `endpoints/auth.py`, `endpoints/insights.py`, `core/config.py`, `core/security.py`, `main.py`, `db/base.py`, `services/ai_insights.py`, `services/notification_service.py`, `services/scheduler.py`, `stores/cartStore.ts`, `vite.config.ts`, `.gitignore`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-15 19:24 UTC | Dex | Added independent V2 production-readiness audit and corrected MEMORY findings | Validate Claude audit against code, reject unsupported claims, and record newly found risks | `docs/audits/2026-05-15-production-readiness-audit-v2.md`, `MEMORY.md` |
| 2026-05-15 19:09 UTC | Audit Agent | Created MEMORY.md | Single source of truth for all agents to understand the codebase | `MEMORY.md` |
| 2026-05-15 19:09 UTC | Audit Agent | Created GO_LIVE_CHECKLIST.md (updated) | Align checklist with audit findings, mark completed items, add audit-driven gates | `docs/GO_LIVE_CHECKLIST.md` |
| 2026-05-15 19:09 UTC | Audit Agent | Updated AGENTS.md and CLAUDE.md | Added mandatory MEMORY.md update rule | `AGENTS.md`, `CLAUDE.md` |
| 2026-05-15 18:19 UTC | Audit Agent | Created production readiness audit | Full evidence-based audit for 5-shop go-live | `docs/audits/2026-05-15-production-readiness-audit.md` |
| 2026-05-15 ~commit 1f14b38 | Developer | Removed backup DB from git | Previous audit flagged `pharma_pos.db.backup` tracked in git | `.gitignore`, removed `pharma_pos.db.backup` |
| 2026-05-01 | Audit Agent | Created first deep codebase audit | Initial evidence-based audit before production hardening | `docs/audits/2026-05-01-deep-codebase-audit.md` |
| Pre-2026-05 | Original Dev | Full system build | Built POS system with FEFO dispensing, audit chain, sync outbox, AI manager, backup/restore, multi-tenant support | All files |
