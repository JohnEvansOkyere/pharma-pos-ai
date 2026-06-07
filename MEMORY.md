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
│       ├── sync_identity_service.py # Stable cross-database UUID and aggregate identity helpers
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

### 2.4 Runtime Boundaries

- `APP_MODE=operational_pos` runs pharmacy workflows against that pharmacy organization's dedicated database.
- `POS_DEPLOYMENT_PROFILE=offline|hosted` selects deployment behavior without changing the tenancy model.
- Customer retention, receipts, follow-ups, outbox delivery, and the hosted browser queue are explicit feature flags.
- `APP_MODE=cloud_reporting` remains the central read/reporting runtime and rejects operational writes.
- Legacy `local_pos` and `online_pos` environment values normalize to `operational_pos` temporarily for migration compatibility.
- Cross-database sync uses control-plane `organization_uid`, `branch_uid`, `deployment_uid`, and `device_uid`; local integer keys remain internal to each operational database.

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

### 3.27 Why LLM Tool Use Replaces Keyword Matching for the CEO AI
The original `_compose_answer` method in `ai_manager_service.py` routes questions via a hardcoded `if/elif` keyword cascade. This is not intelligence — it produces irrelevant template answers for questions that don't match any pattern and silently falls through to a generic default. For a CEO-facing product where AI is the primary value proposition, this is unacceptable.

**Decision:** Replace keyword routing with LLM Tool Use orchestration (OpenAI function-calling / Anthropic tool-use protocol). The LLM receives the question and a set of tool schemas matching the existing validated service functions. It decides which tools to call, calls them, receives the real data, and synthesizes a CEO-appropriate plain-English answer. Questions outside the tool library are answered from the full combined tool results or honestly declined — no wrong template answer.

**Why Tool Use over Text-to-SQL:** Business rules (completed-sales-only revenue, `coalesce(occurred_at, created_at)` time windows, multi-tenant `organization_id` isolation, FEFO-aware stock) are correctly encoded in the existing service functions. Text-to-SQL bypasses those rules and is untestable at scale. Tool Use keeps accuracy guarantees, is testable per-function, is safe against schema changes, and is sandboxed. Text-to-SQL requires a semantic layer to be production-safe — which is effectively tool use at the schema level anyway.

### 3.28 Why the CEO AI Must Be Push-First, Not Pull-Only
A CEO running 5 pharmacy shops will not open the dashboard every morning. Pull-only Q&A (CEO asks → AI answers) is the secondary interface. The primary interface must be proactive: the AI detects anomalies from cloud projection data and pushes alerts to the CEO via Telegram/email without waiting to be asked.

Telegram Bot API is the delivery mechanism of choice: free, reliable, works on any smartphone, no app installation required on the CEO's device, and supports two-way messaging. Alert types: branch silence during trading hours, stockout crossing threshold, revenue drop vs prior period, sync failure, expired batch with positive stock. A daily morning briefing replaces the pull-only dashboard as the CEO's operational pulse.

### 3.29 Why AI Answers Need Server-Side Numeric Verification
Tool use prevents the LLM from querying arbitrary tables, but it does not by itself guarantee that the final prose preserves the exact numbers returned by tools. The chat path therefore verifies numeric claims in the final answer against approved tool evidence before returning it. If an external model states an unsupported figure, the system falls back to the deterministic answer and exposes verification metadata. This keeps the LLM responsible for explanation and prioritization, while backend services remain the source of truth for figures.

### 3.30 Why Two Product Tiers Share One Isolated-Install Architecture
Market feedback confirmed two customer profiles: city pharmacies with stable internet want hosted POS, customer registration, digital receipts, health follow-ups, and live AI; village pharmacies need a fully offline local installation. Both tiers use the same application image and the same isolation boundary: one operational database and backend deployment per pharmacy organization, with branches sharing their organization's database. Village deployments run locally; city deployments are hosted. Both publish audited events to the central reporting plane.

The previous `online_pos` design used one shared Supabase operational database, skipped the outbox, and relied on application-level tenant filtering. That design is superseded by Decisions 3.33 and 3.36. `online_pos` is now only a temporary configuration alias that normalizes to `operational_pos` with the hosted deployment profile. The historical dual/online design documents are explicitly marked superseded.

### 3.31 Why Docker Mode Switching Uses Application-Scoped Environment Profiles
The source-built Docker stack keeps private backend profiles at `backend/.env_local` and `backend/.env_cloud`, copied into `backend/.env`, and browser-safe frontend profiles at `frontend/.env_local` and `frontend/.env_cloud`, copied into `frontend/.env.local`. Both pairs select `operational_pos`; the local pair uses the offline profile with Docker PostgreSQL, while the cloud pair uses the hosted profile and a dedicated managed PostgreSQL `DATABASE_URL`. The frontend must be rebuilt with `--env-file frontend/.env.local` because Vite feature values are compile-time settings.

### 3.32 Why The Transitional Online POS UI Uses One Dashboard Plus An AI Manager Workspace
The hosted `operational_pos` Dashboard is the tenant's single source for live sales, stock, margin, and risk. A compact AI briefing belongs on that Dashboard, while chat, persistent findings, recommendations, and weekly reports belong in a dedicated **AI Manager** workspace. The existing Cloud Dashboard remains specific to `cloud_reporting`, where projected branch data, sync health, reconciliation, and multi-branch owner reporting are valid concerns.

The AI API remains server-side under `/api/ai-manager`; it is not embedded as frontend-only logic. Its reporting data source must be mode-aware: hosted `operational_pos` reads tenant-scoped operational `Sale`, `SaleItem`, `Product`, `ProductBatch`, and inventory movement tables directly, while `cloud_reporting` reads the approved `Cloud*` projection tables. Navigation must not be consolidated until this live-data AI adapter exists.

### 3.33 Why Online Pharmacy Organizations Use Dedicated Operational Databases
At the expected initial scale of roughly ten pharmacy clients, each online pharmacy organization should have its own operational PostgreSQL database. Branches belonging to the same organization share that organization's database. This matches the local-install mental model, structurally prevents cross-organization row access, supports clean offboarding and logical per-client restore, and limits application-data corruption and staged migration failures to one tenant at a time.

The initial implementation should favor one statically configured backend deployment per tenant, using the same versioned application image and a tenant-specific `DATABASE_URL`, instead of introducing request-time database routing before authentication. A control-plane database stores tenant/deployment metadata only. A separate central reporting database receives audited outbox/projection events for vendor fleet reporting; online tenant AI reads its live operational database, while vendor/fleet AI reads the central reporting projections.

This decision does not remove branch-level authorization, customer ownership validation, inventory correctness, audit, or AI data-source work. `ONLINE-P0-01` and `ONLINE-P0-02` become substantially smaller cross-organization risks after physical separation, but `ONLINE-P0-03` through `ONLINE-P0-05` still require explicit fixes. A single managed PostgreSQL server containing multiple tenant databases also shares compute failure and typically cluster/instance-level PITR. It therefore requires encrypted per-database logical backups and restore drills; clients needing independent managed PITR or infrastructure/SLA isolation require a separate project or database cluster.

Hosted Supabase normally treats a project as the unit containing one managed Postgres database and project-level backup/PITR. If Supabase remains the provider, true tenant silos mean project-per-tenant. If cost requires ten databases on one server/cluster, use a managed PostgreSQL provider that explicitly supports that topology and retain the central reporting/control-plane services separately.

### 3.34 Why Branch Assignment Restricts Operational Access
Organization isolation and branch authorization solve different problems. A dedicated operational database prevents cross-pharmacy access, but branches inside one pharmacy organization still share that database. Operational queries therefore apply the authenticated user's organization and, when assigned, branch to sales, products, batches, stock adjustments, stock takes, customers, users, and dashboard aggregates.

A branch-assigned admin or manager remains branch-restricted; role permissions do not silently expand data scope. An organization-level admin is represented by `organization_id` with `branch_id = NULL` and may work across that organization's branches. In the hosted operational profile, an organization-unscoped user is rejected from operational queries instead of receiving unfiltered data.

### 3.35 Why Hosted Tenants Use Separate Render Postgres Instances
Each hosted pharmacy organization uses one paid Render Postgres instance and one Render backend service. Branches in that organization share the database, but different organizations never share an operational database instance. This gives each pharmacy an independent deployment, secret, failure, migration, and restore boundary while reusing the same versioned application image. The existing Supabase project is retained only for the central reporting/control-plane database.

Every hosted operational database uses Render point-in-time recovery plus encrypted off-platform `pg_dump` backups. PITR restores into a new database for validation before connection switching; logical backups provide provider-independent retention and offboarding. No recovery guarantee is considered complete until a real single-tenant restore drill verifies application health, sales totals, batch stock, movement-ledger consistency, and audit integrity without changing another tenant. See `docs/architecture/hosted-tenant-topology-and-backup.md`.

### 3.36 Why Pharmacy Deployments Use One Operational Runtime
`APP_MODE=operational_pos` is the only canonical pharmacy runtime. `POS_DEPLOYMENT_PROFILE=offline|hosted` describes where the backend/database run, while explicit flags control customer retention, receipts, follow-ups, outbox delivery, and the hosted browser queue. Hosted and offline pharmacies therefore share the same transactional behavior and tenancy model.

All operational writes now create transactional outbox events; `CLOUD_SYNC_ENABLED` controls asynchronous delivery to the central plane. The former `local_pos` and `online_pos` values are accepted only as migration aliases and normalize to `operational_pos`. `cloud_reporting` remains separate because it is a central read/reporting boundary that rejects till writes. See `docs/architecture/unified-operational-runtime.md`.

### 3.37 Why Cross-Database Identity Uses Control-Plane UUIDs
Each isolated operational database may assign the same integer primary keys to unrelated organizations, branches, sales, products, or batches. Those integers are therefore database-local implementation details, not fleet identifiers. The control plane allocates stable UUIDs for organization, branch, deployment, and device identity; provisioning must seed the tenant database with the same organization and branch UUIDs.

Every new sync upload carries the complete UUID identity envelope. Central ingestion authenticates the device token, validates those UUIDs against the registered device, and stamps the accepted event with the control-plane organization and branch rows. Submitted numeric organization and branch IDs are retained only for legacy compatibility and are not authoritative when the UUID envelope is present. Business aggregate identity is deterministic UUIDv5 over `(deployment_uid, aggregate_type, local aggregate_id)`, so retries are stable while identical local integers from different deployments cannot collide. See `docs/data/global-identifiers-and-event-identity.md`.

### 3.22 Why AI Provider Selection Is Server-Side
External AI provider and model selection is a vendor/deployment concern, not a pharmacy customer workflow. The cloud dashboard no longer asks tenant admins to choose OpenAI/Claude/Groq or enter model names. `AIProviderPolicyService.resolve_provider()` now auto-selects an available server-side provider from configured API keys, honoring `AI_MANAGER_PROVIDER` when set to a usable provider and otherwise falling back to the first configured provider. `AIManagerLLMProvider` supplies provider-specific default models when `AI_MANAGER_MODEL` is blank. If no external API key is configured, the deterministic offline-safe assistant remains the fallback.

### 3.23 Why The Deployed Cloud App Has A Reporting-Only Mode
The same codebase runs pharmacy operations and the central portal, but those deployments must not behave the same way. `APP_MODE=operational_pos` keeps POS/product/sales workflows available for a dedicated pharmacy database. `APP_MODE=cloud_reporting` makes the backend reject unsafe operational writes, while `VITE_APP_MODE=cloud_reporting` hides and redirects pharmacy routes in the browser. This prevents the central portal from becoming a second till.

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
| CLOUD-P0-02 | 🔴 Critical | Deployed cloud app could look and behave like a separate POS against the cloud DB, creating cloud-only products/sales that confuse the synced reporting source of truth | `main.py`, `app_mode.py`, `App.tsx`, `Sidebar.tsx` | ✅ Fixed with explicit `operational_pos` / `cloud_reporting` modes |
| CLOUD-P0-03 | 🔴 Critical | Cloud "items sold" counted sale lines while local dashboard counted units sold, creating mismatched KPIs for the same synced sales | `cloud_projection_service.py`, `cloud_reconciliation_service.py`, `cloud_reports.py`, `CloudDashboardPage.tsx` | ✅ Fixed; existing projected rows can be repaired with `repair_sale_item_counts` |
| ONLINE-P0-01 | 🔴 Critical | Operational sale, product, stock, customer, and dashboard paths had direct organization/branch object-access bypasses | `sales.py`, `products.py`, `stock_adjustments.py`, `stock_takes.py`, `customers.py`, `dashboard.py` | ✅ Fixed — shared scope helper enforces organization plus assigned branch on reads, writes, reversals, and aggregates |
| ONLINE-P0-02 | 🔴 Critical | Online user administration was not organization/branch scoped and created unscoped users | `users.py`, `models/user.py` | ✅ Fixed — user list/update/delete are scoped and created users inherit the operator's organization/branch |
| ONLINE-P0-03 | 🔴 Critical | Tenant IDs were not consistently propagated through `ProductBatch`, stock source documents, `InventoryMovement`, sync metadata, and audit records | `sales.py`, `products.py`, `stock_adjustments.py`, `stock_takes.py`, `inventory_service.py` | ✅ Fixed — all inventory write paths now carry organization/branch scope before first flush |
| ONLINE-P0-04 | 🔴 Critical | Sale creation accepted arbitrary `customer_id` without verifying active organization/branch ownership before receipt/follow-up workflows | `sales.py`, `customers.py` | ✅ Fixed — sale creation validates the active customer against the cashier's organization and branch before stock mutation |
| ONLINE-P0-05 | 🔴 Critical | Tenant-facing AI currently reads central cloud projection tables instead of its isolated operational database, so online results can be empty or stale | `ai_manager_service.py`, `ai_briefing_service.py`, `ai_weekly_report_service.py`, `cloud_*_service.py` | ⚠️ Accepted — tenant AI must read live operational tables; only vendor/fleet AI should read central projections |
| ONLINE-P1-01 | 🟠 High | `online_pos` offline sale queue is browser IndexedDB only, has no durable invoice/receipt ledger, and failed flushes can be cleared from the UI | `offlineQueue.ts`, `POSPage.tsx`, `OfflineBanner.tsx` | ⚠️ Accepted — only safe as a temporary network-drop buffer |
| ONLINE-P1-02 | 🟠 High | Hosted connectivity check could treat a non-2xx heartbeat response as online | `useOnlineStatus.ts`, `auth.py` | ✅ Fixed — authenticated heartbeat exists and the frontend now requires `response.ok` |
| ONLINE-P1-03 | 🟠 High | Categories and suppliers are global tables with globally unique names, but `online_pos` exposes them as pharmacy-managed resources | `models/category.py`, `models/supplier.py`, `categories.py`, `suppliers.py` | ⚠️ Needs product decision: shared master data vs tenant-owned |
| ONLINE-P0-06 | 🔴 Critical | Sync identity relied on local organization, branch, and aggregate integers that can collide across isolated tenant databases | tenancy/sync models, ingestion, upload, provisioning | ✅ Fixed — control-plane UUID envelope, deployment-scoped aggregate UUID, authenticated central scope stamping, and migration backfill |

---

## 6. Environment & Configuration

### Required Environment Variables (backend/.env)

| Variable                    | Purpose                              | Critical |
| --------------------------- | ------------------------------------ | -------- |
| `DATABASE_URL`              | PostgreSQL connection string — **do NOT set this in client .env files**. config.py builds it from POSTGRES_* vars. A hardcoded DATABASE_URL overrides POSTGRES_PASSWORD silently and causes authentication failures. | ⚠️ Leave unset |
| `SECRET_KEY`                | JWT signing key (min 32 chars)       | ✅       |
| `POSTGRES_DB/USER/PASSWORD` | Docker PostgreSQL setup              | ✅       |
| `APP_MODE`                  | `operational_pos` for pharmacy deployments or `cloud_reporting` for the vendor portal | ✅       |
| `POS_DEPLOYMENT_PROFILE`    | `offline` for on-site backend/database or `hosted` for dedicated Render deployment | ✅       |
| `ENVIRONMENT`               | `production` or `development`        | ✅       |
| `ENABLE_BACKGROUND_SCHEDULER` | Enable APScheduler cron jobs       | ⚠️       |
| `CLOUD_SYNC_ENABLED`        | Enable sync upload to cloud          | Optional |
| `CLOUD_SYNC_ORGANIZATION_UID` / `CLOUD_SYNC_BRANCH_UID` | Control-plane tenant UUIDs used across isolated databases | Required when sync is enabled |
| `CLOUD_SYNC_DEPLOYMENT_UID` / `CLOUD_SYNC_DEVICE_UID` | Stable deployment and device identity for central ingestion | Required when sync is enabled |
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

- Pharmacy installs use `APP_MODE=operational_pos`; hosted/offline and customer/queue behavior come from explicit backend/frontend feature flags.
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
| 2026-06-07 08:18 UTC | Codex | Added globally stable tenant, branch, deployment, device, event, and aggregate identity across the isolated-database sync boundary | Local integer primary keys can repeat in separate pharmacy databases. Control-plane UUIDs now travel in every new upload, central ingestion derives tenant scope from the authenticated device registration, aggregate UUIDs are deterministic per deployment, and existing records receive repeatable migration backfills | tenancy and sync models/schemas/endpoints/services, provisioning and env templates, Alembic migration `q2r3s4t5u6v7`, sync/projection/reporting tests, `docs/data/`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-06-07 08:05 UTC | Codex | Replaced the pharmacy `local_pos` / `online_pos` behavior split with one `operational_pos` runtime and explicit hosted/offline feature flags | Hosted and offline pharmacies must share one tenancy and transactional model. Customer retention, receipts, follow-ups, browser queue, and outbox delivery are now configuration features; all operational writes create outbox events, and old mode values remain migration aliases only | `backend/app/core/app_mode.py`, `backend/app/core/config.py`, `backend/app/services/sync_outbox_service.py`, `backend/app/services/scheduler.py`, `backend/app/services/telegram_alert_service.py`, `backend/app/api/endpoints/sales.py`, `backend/app/api/endpoints/auth.py`, backend/frontend env templates, `docker-compose.yml`, frontend app-mode/routes/sidebar/connectivity/POS files, tests, `docs/architecture/unified-operational-runtime.md`, current architecture/deployment docs, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-06-07 07:55 UTC | Codex | Selected the hosted tenant provider, isolation topology, and backup mechanism and reconciled the Phase 10 topology wording | Separate paid Render Postgres instances provide per-tenant PITR and recovery boundaries at the initial fleet scale. The existing Supabase project remains central reporting/control-plane only; encrypted off-platform logical backups preserve provider-independent recovery and offboarding | `docs/architecture/hosted-tenant-topology-and-backup.md`, `docs/architecture/README.md`, `docs/architecture/system-overview.md`, `docs/architecture/hybrid-cloud-architecture.md`, `docs/architecture/runtime-and-deployment-topology.md`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-06-07 07:51 UTC | Codex | Enforced branch-level authorization across operational routes and dashboard aggregates | Dedicated databases isolate pharmacies, not branches. Branch-assigned users now see and mutate only their branch, organization-level admins retain cross-branch access within their organization, and unscoped online users are rejected | `backend/app/core/app_mode.py`, `backend/app/api/endpoints/sales.py`, `backend/app/api/endpoints/products.py`, `backend/app/api/endpoints/stock_adjustments.py`, `backend/app/api/endpoints/stock_takes.py`, `backend/app/api/endpoints/customers.py`, `backend/app/api/endpoints/users.py`, `backend/app/api/endpoints/dashboard.py`, `backend/tests/test_branch_authorization.py`, `backend/tests/test_inventory_workflows.py`, `docs/data/tenancy-and-branch-scope.md`, `docs/domains/user-and-operator-workflows.md`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-06-07 07:42 UTC | Codex | Completed organization/branch scope propagation across every inventory write path | Batch creation, stock receipt, sale dispense/reversal, manual adjustment, and stock-take correction now keep source documents, batches, movement ledger rows, sync metadata, and audit records in the same scope before first flush | `backend/app/api/endpoints/products.py`, `backend/app/api/endpoints/sales.py`, `backend/app/api/endpoints/stock_adjustments.py`, `backend/app/api/endpoints/stock_takes.py`, `backend/app/core/app_mode.py`, `backend/tests/conftest.py`, `backend/tests/test_inventory_workflows.py`, `backend/tests/test_operational_controls.py`, `backend/tests/test_stock_take_workflows.py`, `docs/domains/inventory-and-stock-control.md`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-06-07 07:31 UTC | Codex | Enforced customer-to-sale organization and branch ownership before stock mutation and reconciled completed Phase 10 architecture decisions | Dedicated tenant databases do not remove branch-level correctness. A cashier can now link only an active customer from the same organization and branch; invalid links cannot alter stock or trigger receipt/follow-up workflows | `backend/app/api/endpoints/sales.py`, `backend/tests/test_inventory_workflows.py`, `docs/domains/customer-retention-and-sale-ownership.md`, `docs/domains/README.md`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-06-06 22:28 UTC | Codex | Reconciled the earlier `online_pos` shared-database decision with the dedicated tenant database architecture | Source review confirms the repository already has most of the isolated-install-to-central-projection pattern. City clients should become hosted isolated installations rather than a second shared-database tenancy model. The current mode is retained temporarily for migration, and remaining branch, event-delivery, customer-ownership, inventory, and tenant-AI work is explicitly preserved | `MEMORY.md` |
| 2026-06-06 22:07 UTC | Codex | Validated the dedicated tenant database plus central reporting decision against published SaaS and retail POS architecture patterns | AWS recognizes silo, pool, and bridge models as valid and notes that real systems commonly mix them; Azure documents database-per-tenant at very large scale; Oracle Retail documents store-level persistence with central systems. The selected architecture is therefore conventional, with static per-tenant backends as an initial simplification rather than the final scaling requirement | `MEMORY.md` |
| 2026-06-06 22:00 UTC | Codex | Revised the long-term cloud tenancy decision from pooled RLS to dedicated operational databases per pharmacy organization | At the expected ten-client scale, structural tenant isolation, offboarding, restore boundaries, and parity with local installations outweigh pooled-schema convenience. The chosen shape uses static per-tenant backend configuration initially, plus separate control-plane and central reporting databases; Supabase would require project-per-tenant rather than assuming ten supported databases inside one project | `MEMORY.md` |
| 2026-06-06 21:52 UTC | Codex | Confirmed the active shared Supabase tenancy model and set the long-term database boundary | The cloud product should use one pooled PostgreSQL database with application ownership checks plus mandatory RLS, separate runtime/migration/platform roles, and adversarial tenant-isolation tests. Database-per-client is reserved for enterprise isolation requirements; the current app-only isolation is not safe for multiple online clients | `MEMORY.md` |
| 2026-06-06 21:28 UTC | Codex | Defined the dashboard and AI placement for `online_pos` and documented the missing online AI data adapter | Online pharmacy operators should use one live operational Dashboard plus a dedicated AI Manager workspace, while projection/sync reporting remains in `cloud_reporting`. Source review found the current AI reads `Cloud*` projection tables even though `online_pos` bypasses projection, so navigation changes are deferred until tenant-scoped live-table reporting is implemented | `MEMORY.md` |
| 2026-06-06 21:30 UTC | Codex | Converted the seeded cloud dataset to JEOCO/Main tenancy, separated tenant and platform admins, fixed PostgreSQL customer enum persistence, and hardened online sale tenant stamping | Customer registration returned 403 because the active admin had no organization; all seeded operational rows were unscoped, and customer insertion then exposed uppercase ORM enum values incompatible with lowercase PostgreSQL enum values. Existing data is now tenant-owned, audit integrity verifies, rollback customer insertion passes, and 43 focused tests pass | Supabase cloud data, `backend/app/models/customer.py`, `backend/app/core/app_mode.py`, `backend/app/api/endpoints/sales.py`, `backend/app/services/inventory_service.py`, `backend/tests/test_app_mode.py`, `backend/tests/test_customer_retention.py`, `MEMORY.md` |
| 2026-06-06 21:18 UTC | Codex | Made the Vite development `/api` proxy derive its target from `VITE_API_URL` | Online local testing runs FastAPI on port 8001, but Vite hardcoded heartbeat and other relative `/api` requests to port 8000, causing `ECONNREFUSED`. TypeScript and the production frontend build pass | `frontend/vite.config.ts`, `MEMORY.md` |
| 2026-06-06 21:14 UTC | Codex | Set the active local-development frontend to `online_pos` while retaining the local API URL on port 8001 | User wanted `.env.local` to use the cloud/city configuration. The browser now calls the local FastAPI process, which connects directly to Supabase through `backend/.env`; no backend secrets were exposed to Vite | `frontend/.env.local`, `MEMORY.md` |
| 2026-06-06 21:10 UTC | Codex | Verified current development runtime mode and account scope | Backend is `online_pos` writing directly to Supabase with cloud sync disabled; active frontend env lacks `VITE_APP_MODE` and therefore defaults to local UI mode; the seeded `admin` is an organization-unscoped platform account rather than a pharmacy tenant operator | `MEMORY.md` |
| 2026-06-06 21:03 UTC | Codex | Migrated the active Supabase cloud database from `m3b4c5d6e7f8` to `p1q2r3s4t5u6` and verified sale-header insertion with a rolled-back transaction | Online POS sale creation failed because the cloud schema lacked the newer `sales.customer_id`, `sales.receipt_sent`, and customer-retention tables expected by current code. All pending migrations completed and a non-persistent insert confirmed the repaired schema | Supabase cloud schema, `MEMORY.md` |
| 2026-06-06 20:45 UTC | Codex | Verified the active cloud database platform-admin identity and confirmed it still accepts the historical seeded demo password | User asked which cloud admin credentials were used; the lookup found one active organization-unscoped admin, so its demo password must be rotated before rollout. The password itself is intentionally not recorded in memory | `MEMORY.md` |
| 2026-06-06 20:41 UTC | Codex | Replaced placeholder JWT secrets in private backend profiles and aligned the active venv to pinned `bcrypt==4.0.1` | Production startup correctly rejected the template `SECRET_KEY`; Passlib also warned because the venv had bcrypt 4.2.0 despite the requirements pin. Verified full Uvicorn startup in `online_pos` mode | `backend/.env`, `backend/.env_local`, `backend/.env_cloud`, `backend/venv`, `MEMORY.md` |
| 2026-06-06 20:28 UTC | Codex | Moved and validated local/cloud environment profiles in their owning backend and frontend directories | User requested server environment files under `backend/` and browser-safe Vite environment files under `frontend/`, with each selected by copying it to that application's main env file; both backend settings profiles and both frontend Compose modes were parsed successfully | `backend/.env_local`, `backend/.env_cloud`, `backend/.env_local.example`, `backend/.env_cloud.example`, `frontend/.env_local`, `frontend/.env_cloud`, `frontend/.env_local.example`, `frontend/.env_cloud.example`, `docker-compose.yml`, `docs/ENVIRONMENT_PROFILES.md`, `README.md`, `MEMORY.md` |
| 2026-06-06 20:10 UTC | Codex | Added private local/cloud Docker profile workflow and removed hardcoded local-mode overrides from the source Compose stack | Local testing must switch predictably between village `local_pos` with Docker PostgreSQL and city `online_pos` with managed PostgreSQL by copying the selected profile into root `.env`; Vite mode must also follow the selected profile at build time | `.env_local`, `.env_cloud`, `.env_local.example`, `.env_cloud.example`, `.env`, `.gitignore`, `docker-compose.yml`, `docs/ENVIRONMENT_PROFILES.md`, `README.md`, `MEMORY.md` |
| 2026-05-29 (this session) | Claude Opus 4.8 | Created the founding master architecture & product roadmap | Founder requested a single end-to-end blueprint (DB, backend, offline, AI, customer retention, project structure, phased roadmap) to be the basis of the business. Grounded in full codebase read + the 2026-05-29 audit + cited research on Ghana/Africa pharma leaders (mPharma Bloom, Field Intelligence Shelf Life, NHIS CLAIM-it/MedSoftwares, MTN MoMo/Hubtel/Paystack, PowerSync vs ElectricSQL, Ghana Data Protection Act 843). Names target stack (PWA + PowerSync offline-first SQLite, pooled RLS Postgres, separate worker), the AI-native plan (forecasting + reorder + pgvector RAG on top of existing deterministic+numeric-verification spine), and the market wedge (NHIS e-claims for cash-flow, demand forecasting, VMI/consignment). Phase 0 = stop-the-bleeding blockers (heartbeat endpoint, composite uniques, RLS, isolation tests). Does not modify code — advisory blueprint only. | `docs/MASTER_ARCHITECTURE_ROADMAP.md`, `MEMORY.md` |
| 2026-05-21 01:53 UTC | Dex | Created the GrejoyPharma Hermes marketing and lead-generation skill | User wanted a comprehensive Hermes skill for this pharmacy POS product to support marketing, lead generation, email/WhatsApp drafting, demos, objections, proposals, pricing drafts, and Ghana/West Africa GTM while keeping claims grounded in implemented product reality. | `/home/grejoy/.hermes/skills/workspace/Grejoypharma/SKILL.md`, `MEMORY.md` |
| 2026-05-20 00:46 UTC | Dex | Added explicit local backup and manual/scheduled cloud-sync operations in Settings | User wanted “cloud backup” to update cloud from local, nightly backup after close, and the local backup button fixed. The implementation now treats cloud update as sync, not backup: Settings has “Sync Local Data to Cloud”, which enqueues a fresh catalog snapshot and uploads pending events; cloud ingestion projects accepted events immediately when projection is enabled; the local scheduler runs the same catalog snapshot sync at 11 PM when cloud sync is enabled. Local backup now falls back to direct `pg_dump` inside Docker, persists to `/app/backups` via compose bind mounts, and schedule helpers default to 11 PM. | `backend/app/api/endpoints/system_ops.py`, `backend/app/api/endpoints/sync.py`, `backend/app/core/config.py`, `backend/app/schemas/system.py`, `backend/app/services/scheduler.py`, `backend/.env.example`, `backend/.env.client.example`, `backend/Dockerfile`, `docker-compose.yml`, `docker-compose.client.yml`, `frontend/src/pages/SettingsPage.tsx`, `frontend/src/pages/SettingsPage.test.tsx`, `frontend/src/services/api.ts`, `install_backup_task.bat`, `scripts/install_backup_cron.sh`, `docs/BACKUP_RESTORE_GUIDE.md`, `docs/WINDOWS_LOCAL_DEPLOYMENT_RUNBOOK.md`, `docs/operations/cloud-operations.md`, `MEMORY.md` |
| 2026-05-20 00:36 UTC | Dex | Confirmed current backup behavior and gaps | User asked whether Back Up Now is local, whether cloud backup exists, and whether nightly backups already run. Review confirmed the Settings button triggers local PostgreSQL dump scripts only; nightly backup is installed by OS helpers (`install_backup_task.bat` or `scripts/install_backup_cron.sh`), not by the app scheduler; cloud backup is not implemented in application code and must be handled through the managed cloud database/provider or a new explicit cloud backup workflow. | `MEMORY.md` |
| 2026-05-20 00:26 UTC | Dex | Diagnosed local/cloud product catalog mismatch after client seeding | User clarified the client laptop was seeded locally, then the cloud DB was separately seeded, producing placeholder/product-mismatched cloud rows. Diagnosis: cloud product state is `cloud_product_snapshots` projected from uploaded local sync events, not an automatic mirror of local `products`; separate cloud seeding can create divergent rows, and local seed scripts do not necessarily create product sync events unless a full catalog snapshot is enqueued, uploaded, and projected. | `MEMORY.md` |
| 2026-05-20 00:09 UTC | Dex | Prepared the AI hardening and architecture documentation work for push to `origin/main` | User asked to push the current AI-layer changes. This records the release-control action before committing and pushing the completed verification, code, checklist, and architecture updates. | `MEMORY.md` |
| 2026-05-20 00:05 UTC | Dex | Updated the AI architecture document to match the current tool-use implementation | The untracked AI architecture note was stale: it still described the chat path mainly as keyword routing and had an incorrect Telegram endpoint grouping. The doc now records the implemented response contract, tool traceability, numeric verification fallback, correct Telegram webhook path, and remaining AI rollout gaps. | `docs/AI_ARCHITECTURE.md`, `MEMORY.md` |
| 2026-05-20 00:01 UTC | Dex | Hardened AI chat trust layer with numeric verification, tool traceability, and Telegram reply routing support | The CEO-facing AI now exposes which tools were called, verifies final numeric claims against approved evidence before returning external LLM answers, falls back on unsupported figures, and allows Telegram org-scoped replies to call the AI without an interactive user session. Regression tests cover verification, tool trace, Telegram routing, and midnight-safe today windows. | `backend/app/schemas/ai_manager.py`, `backend/app/services/ai_llm_provider.py`, `backend/app/services/ai_manager_service.py`, `backend/tests/test_ai_manager.py`, `frontend/src/pages/CloudDashboardPage.tsx`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-19 23:51 UTC | Dex | Re-audited the improved AI layer and identified remaining gaps | User asked what is still missing after improvements. Review confirmed tool-use orchestration, proactive Telegram alerting, and daily briefing scaffolding exist, but found remaining gaps around final-answer verification, structured evidence/output, actual tool-call traceability, broader tool coverage, Telegram reply runtime wiring, and missing tests for the new alert/reply paths. | `MEMORY.md` |
| 2026-05-19 22:30 UTC | Claude Sonnet 4.6 | Implemented Phase 9.2: Telegram bot adapter, proactive anomaly alerts, daily briefing, and CEO webhook chat routing | CEO confirmed delivery architecture: Telegram for two-way conversation + push alerts; Email for scheduled reports. Built: `TelegramService` (HTTP adapter, format_alert, format_briefing), `TelegramAlertService` (anomaly detection with 4h deduplication, daily briefing dispatch, CEO message routing into AIManagerService), `POST /api/telegram/webhook` (receives CEO Telegram messages, replies via background task), `TelegramAlertLog` model + Alembic migration `n4c5d6e7f8g9`, scheduler jobs `push_telegram_alerts` (every 45min) and `send_daily_briefing` (daily 08:00), new config vars: `TELEGRAM_ALERTS_ENABLED`, `TELEGRAM_ALERT_COOLDOWN_HOURS`, `TELEGRAM_ALERT_INTERVAL_MINUTES`, `TELEGRAM_WEBHOOK_SECRET`, `AI_DAILY_BRIEFING_ENABLED`, `AI_DAILY_BRIEFING_HOUR`, `AI_DAILY_BRIEFING_PERIOD_DAYS`. All 22 AI manager tests still pass. | `backend/app/services/telegram_service.py` (new), `backend/app/services/telegram_alert_service.py` (new), `backend/app/api/endpoints/telegram.py` (new), `backend/alembic/versions/n4c5d6e7f8g9_add_telegram_alert_log.py` (new), `backend/app/models/ai_report.py`, `backend/app/models/__init__.py`, `backend/app/core/config.py`, `backend/app/services/scheduler.py`, `backend/app/api/__init__.py`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-19 21:04 UTC | Dex | Audited current LLM tool-use AI setup without changing application code | User asked for a blunt review of the new tool-calling AI path. Review found the setup is a meaningful architectural improvement over keyword routing, but still lacks answer verification, broad tool coverage, structured answer schemas, and end-to-end real provider tests needed for a top-tier pharmacy data analyst. | `MEMORY.md` |
| 2026-05-19 20:30 UTC | Claude Sonnet 4.6 | Implemented Phase 9.1: LLM Tool Use Architecture — replaced keyword matching with real function-calling orchestration | CEO AI is the product's primary value proposition. The old `_compose_answer` keyword cascade returned irrelevant templates for unrecognised questions. New architecture: 10 service functions formalised as `TOOL_SCHEMAS` (OpenAI function-calling format); `generate_answer_with_tools` added to `ai_llm_provider.py` with `_openai_tool_loop` (OpenAI + Groq), `_claude_tool_loop`, and `_to_anthropic_tools`; `_ceo_system_prompt` replaces constraining `_provider_prompt`; `_make_tool_dispatcher` serves pre-fetched data for default period calls (zero extra DB round-trips) and does live queries for today/yesterday; `answer()` splits into LLM path (tool-use) and deterministic fallback (`_compose_answer` kept for no-key/offline safety); all 22 existing tests pass. | `backend/app/services/ai_llm_provider.py`, `backend/app/services/ai_manager_service.py`, `backend/tests/test_ai_manager.py`, `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-19 19:55 UTC | Dex | Audited current AI manager behavior against the requested data-analyst expectation | The user asked whether the AI can answer broad pharmacy/database questions without hardcoded answers or guessed figures. Review found the current assistant is safe and data-grounded for a fixed set of cloud reporting intents, with conversation persistence and trust warnings, but it is not yet a general natural-language database analyst. | `MEMORY.md` |
| 2026-05-19 UTC | Claude Sonnet 4.6 | Documented CEO AI architecture decision: LLM Tool Use replaces keyword matching; push-first alert model added | CEO is the primary user of the cloud AI. Keyword-matching `_compose_answer` is not intelligence — it returns irrelevant templates for unrecognized questions. LLM Tool Use (OpenAI function-calling / Anthropic tool-use) lets the LLM decide which validated service functions to call and reason freely over combined results. Text-to-SQL rejected: business rules are in service functions; Text-to-SQL bypasses them and is untestable. Push-first alerts (Telegram) added as primary interface because CEOs won't open the dashboard daily. Checklist Phase 9 added. Design decisions 3.27 and 3.28 added. | `docs/GO_LIVE_CHECKLIST.md`, `MEMORY.md` |
| 2026-05-19 19:48 UTC | Dex | Fixed AI manager time-window intent and products-sold answers | The cloud chat answered "today" questions using the dashboard's default 30-day scope and answered "what drugs did we sell" from stock-risk rows. AI manager now recognizes today/yesterday reporting windows, scopes sales/inventory/product-sales evidence to that window, adds a dedicated product_sales evidence pack from sale movement facts, and prompts external LLMs not to replace today with 30 days or stock risk with sold products. Regression tests cover total sales today and drugs sold today. | `backend/app/services/ai_manager_service.py`, `backend/tests/test_ai_manager.py`, `MEMORY.md` |
| 2026-05-19 18:39 UTC | Dex | Added product identity to sale sync payloads and placeholder cloud projection | Cloud was showing `Product 1`, `Product 2`, etc. when sale events reached the cloud before product catalog snapshot events. New sale-created sync payloads now include product name and SKU, and the cloud projector uses those fields only to replace generic placeholder product snapshots. Existing placeholder rows still require the one-time local catalog snapshot enqueue/upload/projection repair. | `backend/app/api/endpoints/sales.py`, `backend/app/services/cloud_projection_service.py`, `backend/tests/test_sales_financial_integrity.py`, `backend/tests/test_cloud_projection_service.py`, `MEMORY.md` |
| 2026-05-19 18:37 UTC | Dex | Reverted Render startup to direct Uvicorn and documented manual Supabase migrations | Render free-tier startup could not reliably run Alembic before binding the web service port. Cloud schema migrations should be run manually from a trusted machine using the Supabase `DATABASE_URL`; Render then starts the API quickly with Uvicorn. | `render.yaml`, `docs/operations/render-vercel-deployment.md`, `MEMORY.md` |
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
| 2026-05-28 00:55 UTC | Antigravity | Created dual-mode deployment plan and architecture decision | Market feedback: city pharmacies need online-first with customer retention (registration, receipts, health follow-ups); village pharmacies need offline-first. Documented three APP_MODE tiers (local_pos, online_pos, cloud_reporting), customer retention module roadmap, offline fallback queue design, and migration paths. Added design decision 3.30. | `docs/DUAL_MODE_DEPLOYMENT_PLAN.md`, `MEMORY.md` |
| 2026-05-28 01:09 UTC | Antigravity | **Phase A executed: online_pos mode added to backend and frontend** | Added `online_pos` to VALID_APP_MODES and config validator. Write guard allows all POS ops in online_pos. Sync outbox short-circuits (returns None) in online_pos — no local event accumulation. Scheduler skips sync upload/heartbeat/catalog-snapshot/projection jobs in online_pos. Frontend: isPosMode, isOnlinePosMode exports; routes and sidebar show full POS + cloud dashboard; footer shows "Online" label. All 137 backend tests pass, TypeScript compiles cleanly. | `app_mode.py`, `config.py`, `sync_outbox_service.py`, `scheduler.py`, `appMode.ts`, `App.tsx`, `Sidebar.tsx`, `test_app_mode.py`, `.env.example`, `.env.client.example` |
| 2026-05-28 09:37 UTC | Antigravity | **Phase A (org scoping) + Phase B (offline fallback queue) executed** | Org scoping: `apply_tenant_scope()` added to `app_mode.py` — stamps organization_id/branch_id from the authenticated user onto Sale, Product, and StockAdjustment records in online_pos mode. List/search queries also scoped by org in online_pos mode. Phase B: `offlineQueue.ts` (IndexedDB-backed FIFO queue), `useOnlineStatus.ts` (navigator.onLine + API heartbeat every 15s), `OfflineBanner.tsx` (offline/flushing/success states), MainLayout wires banner site-wide. POSPage queues sales to IndexedDB when offline and shows inline badge. Auto-flush drains queue on reconnect with retry and failure tracking. All 137 backend tests pass, TypeScript compiles cleanly (0 errors). | `app_mode.py`, `sales.py`, `products.py`, `stock_adjustments.py`, `offlineQueue.ts`, `useOnlineStatus.ts`, `OfflineBanner.tsx`, `MainLayout.tsx`, `POSPage.tsx` |
| 2026-05-28 09:37 UTC | Antigravity | **Phase A (org scoping) + Phase B (offline fallback queue) executed** | Org scoping: `apply_tenant_scope()` added to `app_mode.py` — stamps organization_id/branch_id from the authenticated user onto Sale, Product, and StockAdjustment records in online_pos mode. List/search queries also scoped by org in online_pos mode. Phase B: `offlineQueue.ts` (IndexedDB-backed FIFO queue), `useOnlineStatus.ts` (navigator.onLine + API heartbeat every 15s), `OfflineBanner.tsx` (offline/flushing/success states), MainLayout wires banner site-wide. POSPage queues sales to IndexedDB when offline and shows inline badge. Auto-flush drains queue on reconnect with retry and failure tracking. All 137 backend tests pass, TypeScript compiles cleanly (0 errors). | `app_mode.py`, `sales.py`, `products.py`, `stock_adjustments.py`, `offlineQueue.ts`, `useOnlineStatus.ts`, `OfflineBanner.tsx`, `MainLayout.tsx`, `POSPage.tsx` |
| 2026-05-28 09:47 UTC | Antigravity | Created `docs/ONLINE_FIRST_ARCHITECTURE.md` | Comprehensive technical reference for the online_pos mode — covers rationale, all backend/frontend changes, tenant isolation, offline queue API, deployment guide, file map, testing instructions, and known limitations. Written so any future agent can pick up the work without reading source code. Updated MEMORY.md decision 3.30 and README.md docs list. | `docs/ONLINE_FIRST_ARCHITECTURE.md`, `MEMORY.md`, `README.md` |
| 2026-05-28 17:38 UTC | Antigravity | **Phase C executed: Customer Retention Module** | Backend: `Customer` and `CustomerFollowUp` models + Alembic migration. `customer_id` FK + `receipt_sent` flag added to `Sale`. `message_adapter.py` — abstract `MessageAdapter` base + `StubAdapter` + `get_adapter()` factory. `customer_retention_service.py` — `schedule_follow_up()`, `dispatch_receipt()`, `process_pending_follow_ups()`. Customers CRUD API. `sales.py` wired to link customer_id, dispatch receipt, and schedule follow-up. Hourly scheduler job. Frontend: `CustomerModal.tsx`, `CustomersPage.tsx`, `FollowUpDashboard.tsx`, Sidebar + App.tsx + POSPage updates. 137 tests pass, TS 0 errors. | `customer.py`, `sale.py`, `customers.py` endpoint, `scheduler.py`, `CustomerModal.tsx`, `CustomersPage.tsx`, `FollowUpDashboard.tsx`, `Sidebar.tsx`, `App.tsx`, `POSPage.tsx`, `api.ts` |
| 2026-05-28 17:49 UTC | Antigravity | **Phase D executed: Customer Analytics** | `customer_analytics_service.py` — `summary()`, `top_customers_by_spend()`, `top_products_by_customer_reach()`. `GET /customers/analytics` endpoint. `get_customer_analytics` AI tool. Telegram daily briefing retention block. `CustomerAnalyticsPage.tsx` — period selector, KPI cards, lifecycle funnel, consent panel, leaderboard, affinity table. Sidebar + App.tsx + `api.ts`. 137 tests pass, TS 0 errors. | `customer_analytics_service.py`, `customers.py`, `ai_manager_service.py`, `telegram_alert_service.py`, `CustomerAnalyticsPage.tsx`, `Sidebar.tsx`, `App.tsx`, `api.ts` |
| 2026-05-29 06:10 UTC | Antigravity | **Phase E: Provider integration + tests** | `_africas_talking_adapter.py` — Ghana number normalisation (0244→+233, E.164, 233-prefix, 00-prefix), AT statusCode handling (101/102=sent/queued), WhatsApp→SMS fallback, sender ID cap at 11 chars. `message_adapter.py` updated: reads `settings.SMS_PROVIDER`; Hubtel provider path wired; split ImportError/KeyError logging. `config.py`: 9 new typed SMS settings (`SMS_PROVIDER`, `SMS_SENDER_ID`, `SMS_API_KEY`, `SMS_USERNAME`, `SMS_FROM_NUMBER`, `SMS_CLIENT_ID`, `SMS_CLIENT_SECRET`, `CUSTOMER_FOLLOWUP_DAYS`, `CUSTOMER_FOLLOWUP_HOUR`). `test_customer_retention.py`: 21 tests covering registration, consent, analytics (7 scenarios), StubAdapter, get_adapter fallback, AT normalisation. `GO_LIVE_CHECKLIST.md`: Phase E section added (E.1–E.7). Full suite: **158 tests pass**. | `_africas_talking_adapter.py`, `message_adapter.py`, `config.py`, `test_customer_retention.py`, `GO_LIVE_CHECKLIST.md` |
| 2026-05-29 06:41 UTC | Codex | Added independent verification audit comparing Claude's 2026-05-29 architecture audit against source code | User requested an independent audit first, then claim-by-claim verification of Claude's report. Confirmed several Claude findings, rejected the migration-chain and heartbeat-fallback mechanisms, and recorded skipped critical `online_pos` tenant-isolation defects. | `docs/audits/2026-05-29-independent-architecture-audit-verification.md`, `MEMORY.md` |
| 2026-05-30 10:40 UTC | Antigravity | **Audit hardening pass (2026-05-29 audit)** | Fixed 7 of 16 audit findings. **C-01** — migration `p1q2r3s4t5u6` drops global unique constraints on sku/barcode/username/email, re-creates as composite `(organization_id, X)` with PG15 `NULLS NOT DISTINCT` / PG14 `COALESCE(-1)` fallback. **H-01** — same migration adds PostgreSQL `set_updated_at()` trigger + per-table triggers on 5 tables. **H-02** — 6 composite indexes added with `CONCURRENTLY` (commits transaction first). **H-04** — `sales.py:446` invoice number fixed to `datetime.now(timezone.utc)`. **H-05** — `_LLMCircuitBreaker` in `ai_llm_provider.py`: 3-failure threshold, 300s open window, thread-safe `RLock`. **H-07** — deleted `pharma_pos.db`/`.backup`; `.dockerignore` extended. C-02 and H-08 deferred. 158 tests pass. | `p1q2r3s4t5u6_production_schema_hardening.py`, `sales.py`, `ai_llm_provider.py`, `.dockerignore`, audit doc |
| 2026-05-31 09:38 UTC | Antigravity | **Offline queue hardening + AI rate limiting (C-02/M-10)** | **C-02 mitigated**: `offlineQueue.ts` — provisional invoice numbers (`generateLocalInvoice()`, `TMP-YYYYMMDD-XXXXXX`), `failedCount()`, `retryFailed(id)`, `retryAllFailed()`, `removeItem(id)`, `exportFailed()` (JSON download), `exportAll()`; DB schema bumped to v2. `POSPage.tsx` — stamps local invoice at queue time, shows it in toast. New `OfflineQueuePage.tsx` — operator dashboard: KPI tiles, flush, retry-all, export, delete, payload inspector, durability disclaimer. Wired into sidebar (`FiInbox`) + App.tsx (`/offline-queue`, admin/manager). **M-10 resolved**: `ai_manager.py` — per-user sliding-window rate limiter on `POST /ai-manager/chat`, 10 req/60s, HTTP 429. `test_ai_manager.py` — `autouse` fixture `_reset_ai_rate_limiter` prevents test cross-contamination. `.env.client.example` — SMS provider settings documented. 158 tests pass, TS 0 errors. | `offlineQueue.ts`, `POSPage.tsx`, `OfflineQueuePage.tsx`, `Sidebar.tsx`, `App.tsx`, `ai_manager.py`, `test_ai_manager.py`, `.env.client.example`, audit doc |
| Pre-2026-05 | Original Dev | Full system build | Built POS system with FEFO dispensing, audit chain, sync outbox, AI manager, backup/restore, multi-tenant support | All files |
