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
│   │   ├── cloud_projection.py  # CloudSaleFact, CloudProductSnapshot, etc.
│   │   ├── ai_report.py         # AIWeeklyManagerReport, delivery settings
│   │   ├── stock_adjustment.py  # StockAdjustment, AdjustmentType
│   │   ├── stock_take.py        # StockTake, StockTakeItem
│   │   ├── restore_drill.py     # RestoreDrill (backup verification tracking)
│   │   ├── notification.py      # Notification, NotificationType
│   │   ├── category.py          # Category
│   │   └── supplier.py          # Supplier
│   ├── schemas/                 # 17 Pydantic schema files (request/response)
│   ├── api/
│   │   ├── __init__.py          # api_router with all 15 endpoint routers
│   │   ├── dependencies/        # Auth dependencies (get_current_user, require_*)
│   │   └── endpoints/           # 15 endpoint modules
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
│   └── services/                # 14 service modules
│       ├── audit_service.py     # Tamper-evident SHA-256 hash chain audit logging
│       ├── inventory_service.py # FEFO batch queries, stock recalculation, movement records
│       ├── sync_outbox_service.py # Monotonic sequence + payload hash outbox events
│       ├── sync_upload_service.py # Upload pending sync events to cloud API
│       ├── cloud_projection_service.py # Project ingested events into reporting tables
│       ├── cloud_reconciliation_service.py # Cross-check local vs cloud data
│       ├── notification_service.py # Background expiry/low-stock/dead-stock alerts
│       ├── scheduler.py         # APScheduler background jobs
│       ├── ai_manager_service.py # Deterministic + LLM manager assistant
│       ├── ai_llm_provider.py   # OpenAI/Claude/Groq HTTP adapters
│       ├── ai_provider_policy_service.py # Tenant-level AI provider policy
│       ├── ai_weekly_report_service.py # Weekly manager report generation
│       ├── ai_report_delivery_service.py # Email/Telegram delivery with retries
│       └── ai_insights.py       # Rule-based dead stock, reorder, sales patterns
├── alembic/                     # Database migrations (PostgreSQL)
│   └── env.py                   # ⚠️ KNOWN ISSUE: imports only 10 of 25 models
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

---

## 4. Critical Business Rules

1. **FEFO dispensing is mandatory** — stock must be dispensed from nearest-expiry batch first
2. **Sales are transaction-safe** — `with_for_update()` row locking on products and batches during sale creation
3. **Only COMPLETED sales should count in revenue** — `SaleStatus.COMPLETED` is the only valid state for financial reporting
4. **User provisioning is admin-controlled** — no public registration endpoint exists
5. **Prescription-only products require prescription validation** — `PrescriptionStatus.PRESCRIPTION_ONLY` and `is_narcotic` fields exist but **enforcement is not yet implemented** (P1-03 in audit)
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
| P1-03  | 🔴 Critical | No server-side prescription enforcement      | `endpoints/sales.py:264+`  | ✅ Fixed    |
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

---

## 6. Environment & Configuration

### Required Environment Variables (backend/.env)

| Variable                    | Purpose                              | Critical |
| --------------------------- | ------------------------------------ | -------- |
| `DATABASE_URL`              | PostgreSQL connection string         | ✅       |
| `SECRET_KEY`                | JWT signing key (min 32 chars)       | ✅       |
| `POSTGRES_DB/USER/PASSWORD` | Docker PostgreSQL setup              | ✅       |
| `ENVIRONMENT`               | `production` or `development`        | ✅       |
| `ENABLE_BACKGROUND_SCHEDULER` | Enable APScheduler cron jobs       | ⚠️       |
| `CLOUD_SYNC_ENABLED`        | Enable sync upload to cloud          | Optional |
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
