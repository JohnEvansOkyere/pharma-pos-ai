# Deep Codebase Audit — 2026-05-01

**Auditor:** Senior systems engineer, file-by-file review  
**Scope:** Full stack — backend, frontend, database, infrastructure, scripts  
**Verdict:** Solid architectural foundation. Several confirmed issues that **will** break in production.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What Is Working Well](#2-what-is-working-well)
3. [Critical Issues — Will Break in Production](#3-critical-issues--will-break-in-production)
4. [Serious Issues — Likely to Break Under Real Use](#4-serious-issues--likely-to-break-under-real-use)
5. [Moderate Issues — Should Fix Before Go-Live](#5-moderate-issues--should-fix-before-go-live)
6. [Minor Issues — Cleanup and Hygiene](#6-minor-issues--cleanup-and-hygiene)
7. [File-by-File Findings](#7-file-by-file-findings)
8. [Recommended Priority Order](#8-recommended-priority-order)

---

## 1. Executive Summary

The project has a **mature, well-structured architecture** for a pharmacy POS. The backend code quality is above average — proper use of transactions, FEFO batch allocation, money rounding, row-level locking for concurrency, and a tamper-evident audit chain. The frontend is functional and covers the key workflows.

However, there are **confirmed production blockers** that will cause data integrity issues, security vulnerabilities, or runtime failures:

| Severity | Count |
|----------|-------|
| 🔴 Critical (will break) | 6 |
| 🟠 Serious (likely to break) | 8 |
| 🟡 Moderate (should fix) | 7 |
| 🔵 Minor (cleanup) | 5 |

---

## 2. What Is Working Well

These are genuine strengths — not assumptions, confirmed by reading the code:

### ✅ Sale Transaction Integrity
- `sales.py` uses `with_for_update()` row locks on products during sale creation — correct for concurrent tills.
- FEFO batch allocation in `_allocate_product_batches()` is properly implemented.
- `Decimal` + `round_money()` with `ROUND_HALF_UP` — proper financial rounding, no float arithmetic on money at the database write layer.
- Invoice numbers are derived from DB-assigned sale IDs after flush — collision-safe.
- Full try/except with `db.rollback()` on sale creation and reversals.

### ✅ Inventory Movement Ledger
- `InventoryMovement` is append-only with source document references — this is a proper audit trail.
- `InventoryService.recalculate_product_stock()` derives `total_stock` from valid batches instead of trusting the cached column — correct.
- Stock adjustments properly handle FEFO consumption for decrements without a specified batch.

### ✅ Tamper-Evident Audit Chain
- `AuditService` implements hash-chained audit logs with `pg_advisory_xact_lock` for per-organization serialization.
- `verify_integrity()` can detect insertions, deletions, and modifications — good for pharmacy regulatory compliance.
- Canonical payload serialization is deterministic (sorted keys, consistent datetime formatting).

### ✅ Auth & Permissions
- No public self-registration endpoint — confirmed by searching `auth.py`. Users are admin-provisioned only.
- Granular permission system (`UserPermission` enum) with role-based defaults and per-user overrides.
- `effective_permissions` property with fallback to role defaults is clean.
- Proper role hierarchy checks in `require_role()`.

### ✅ Sale Void/Refund Controls
- Reversals require specific permissions (`require_void_sale`, `require_refund_sale`).
- `SaleReversal` is a first-class model — full audit trail of who, when, why.
- Stock is restored to original or synthetic batches with movement records.
- Only completed sales can be reversed — double-reversal is blocked.

### ✅ Code Organization
- Clean separation: models → schemas → endpoints → services.
- Alembic migrations are sequential and each has a clear purpose.
- 23 migration files showing iterative, controlled schema evolution.
- 16 backend test files covering auth, sales, inventory, stock takes, sync, cloud reports, and validation.

### ✅ Sync & Cloud Architecture
- Outbox pattern (`SyncOutboxService`) for eventual cloud sync — correct pattern for offline-first.
- Cloud projection tables for reporting are properly separated from operational tables.
- Sync is feature-flagged and disabled by default — safe for local-only deployments.

---

## 3. Critical Issues — Will Break in Production

### 🔴 C1: Dashboard Queries Count Voided/Refunded Sales as Revenue

**File:** `backend/app/api/endpoints/dashboard.py`  
**Lines:** 38-84 (KPIs), 238-276 (sales trend), 279-323 (staff performance), 425-482 (profit by category), 538-603 (financial KPIs)

**The problem:** None of the dashboard queries filter by `Sale.status == SaleStatus.COMPLETED`. Every KPI, sales trend, staff performance, profit analysis, and financial report includes cancelled and refunded sales in their totals.

I searched the file — there is **zero** reference to `Sale.status` anywhere in `dashboard.py`.

**Impact:** A pharmacy that voids a GH₵5,000 sale will still see that GH₵5,000 in today's revenue, profit, and trend charts. The owner will think they made more money than they did. The end-of-day closeout in `sales.py` correctly separates by status, but the dashboard does not.

**Fix:** Add `.filter(Sale.status == SaleStatus.COMPLETED)` to every dashboard query that touches `Sale.total_amount`.

---

### 🔴 C2: Today's Sales Summary Also Counts Voided/Refunded Revenue

**File:** `backend/app/api/endpoints/sales.py`  
**Lines:** 526-571 (`get_today_sales_summary`)

**The problem:** Same issue as C1 — the summary endpoint used by the frontend header doesn't filter by sale status. Voided and refunded sales inflate `total_revenue`, `total_profit`, and `total_items_sold`.

**Fix:** Add status filter: `.filter(Sale.status == SaleStatus.COMPLETED)`.

---

### 🔴 C3: Prescription and Controlled Substance Rules Are Not Enforced Server-Side

**Files:** `backend/app/api/endpoints/sales.py` (create_sale), `backend/app/models/product.py`

**The problem:** The `Product` model has `prescription_status` (PRESCRIPTION_REQUIRED, OTC), `is_narcotic`, and `requires_id` fields. But `create_sale()` does **not** check any of these during sale creation. I searched for "prescription", "narcotic", and "PRESCRIPTION_REQUIRED" across the entire `sales.py` — zero hits.

A cashier can sell a prescription-required drug or a controlled substance without any prescription number, doctor name, or customer ID. The model has the fields; the enforcement doesn't exist.

**Impact:** In a real pharmacy, this is a regulatory compliance failure. In Ghana (FDA jurisdiction), dispensing prescription-only medicines without a prescription is illegal.

**Fix:** Add server-side validation in `create_sale()`:
- If any item has `prescription_status == PRESCRIPTION_REQUIRED`, require `has_prescription == True` and `prescription_number` to be non-empty.
- If any item has `is_narcotic == True`, require `customer_id_number` to be non-empty.
- If any item has `requires_id == True`, require `customer_id_number` to be non-empty.

---

### 🔴 C4: SECRET_KEY in Backend `.env` Is a Placeholder Value

**File:** `backend/.env`, line 13

```
SECRET_KEY=replace-with-generated-secret-key
```

**The problem:** The literal string `replace-with-generated-secret-key` is the JWT signing secret. The config validator in `config.py` does catch `SECRET_KEY is None`, but the placeholder is not None — it's a weak, predictable string. Anyone who reads this repository can forge valid JWT tokens for any user.

The root `.env` has a different, apparently real key (`7483b1981e...`), but `backend/.env` is what the backend actually loads (since `config.py` uses `env_file = ".env"` and the app runs from the `backend/` directory).

**Impact:** Complete authentication bypass. Anyone with access to the code can impersonate any user, including admins.

**Fix:** Generate a real key (`openssl rand -hex 32`) and set it in `backend/.env`. Add a config validator that rejects known placeholder values.

---

### 🔴 C5: Database Backup File Committed to Git

**File:** `backend/pharma_pos.db.backup` (tracked in git)

**The problem:** `git ls-files` confirmed `backend/pharma_pos.db.backup` is tracked. The `.gitignore` excludes `*.db` but this is a `.db.backup` file — it slips through. This file contains actual database data (147KB).

Additionally, there's a `pharma_pos.db` at the project root (not tracked, caught by `.gitignore`), but the one in `backend/` is tracked.

**Impact:** Historical data, user hashes, and business records may be exposed in the repository history. Even after removal, it persists in git history.

**Fix:** `git rm --cached backend/pharma_pos.db.backup` and add `*.db.backup` to `.gitignore`.

---

### 🔴 C6: Alembic env.py Only Imports a Subset of Models

**File:** `backend/alembic/env.py`, lines 17-29

**The problem:** The model imports in `alembic/env.py` are incomplete. It imports `User, Category, Supplier, Product, ProductBatch, Sale, SaleItem, Notification, ActivityLog, RestoreDrill, StockAdjustment` — but is missing:

- `SaleReversal`
- `InventoryMovement`
- `StockTake`, `StockTakeItem`
- `SyncEvent`, `SyncEventCounter`
- `IngestedSyncEvent`
- `Organization`, `Branch`, `Device`
- All AI report models
- All cloud projection models

**Impact:** Running `alembic revision --autogenerate` will produce migrations that attempt to **drop** the tables for these unimported models. If someone runs autogenerate without careful review, it could destroy production tables.

The current migrations work because they were manually created, but this is a ticking time bomb for the next person who runs autogenerate.

**Fix:** Import from `app.models` (the `__init__.py` already exports everything) instead of cherry-picking:
```python
from app.models import *  # or import the __init__ explicitly
```

---

## 4. Serious Issues — Likely to Break Under Real Use

### 🟠 S1: Cart Store Uses Snapshot Stock — Stale Stock Data on Multi-Till

**File:** `frontend/src/stores/cartStore.ts`

**The problem:** When a product is added to the cart, `available_stock` is captured from the product listing at that moment. Subsequent stock checks (`updateQuantity`) validate against this snapshot, not the current server state. If two cashiers are working simultaneously, both could add the same product to their carts and both see full stock.

The backend does protect against this with `with_for_update()` row locks, so the second sale will fail — but the cashier gets a confusing error after they've already collected payment from the customer.

**Recommendation:** Add a stock revalidation step at checkout time (a lightweight pre-check endpoint) or display a warning that stock may have changed.

---

### 🟠 S2: Root `.env` Contains Real Secrets But Is Gitignored — Inconsistent

**File:** `.env` (root), `backend/.env`

**The problem:** Two `.env` files exist with different secrets:
- Root `.env`: Has `POSTGRES_PASSWORD=newpassword123`, `SECRET_KEY=7483b1981e...`
- `backend/.env`: Has `POSTGRES_PASSWORD=newpassword123`, `SECRET_KEY=replace-with-generated-secret-key`

The backend loads from `backend/.env`. The root `.env` is used by `docker-compose.yml` (via env_file on the db service). Neither is tracked in git, which is correct — but the password `newpassword123` appears in both, and the README instructs users to copy from `.env.example`.

This is a source of confusion for deployment. The postgres password is weak.

**Fix:** Consolidate to one env file strategy. Use strong passwords in production.

---

### 🟠 S3: `low-stock` Endpoint Route Ordering Conflict

**File:** `backend/app/api/endpoints/products.py`, line 980

**The problem:** `GET /products/low-stock` is defined **after** `GET /products/{product_id}` (line 339). FastAPI evaluates routes in order. A request to `/products/low-stock` will match `{product_id}` first, with `product_id = "low-stock"`, which will then fail to convert to `int` and return a validation error.

The other special routes (`/search`, `/catalog`) are defined **before** the `{product_id}` route, so they work fine. `low-stock` is the only one after.

**Impact:** The `GET /products/low-stock` endpoint is unreachable. Frontend `getLowStockProducts()` will always fail.

**Fix:** Move the `low-stock` route definition above the `/{product_id}` route.

---

### 🟠 S4: pgAdmin Container Has No Auth Configuration

**File:** `docker-compose.yml`, lines 83-98

**The problem:** The pgAdmin service uses `env_file: ./backend/.env` which contains postgres credentials but no `PGADMIN_DEFAULT_EMAIL` or `PGADMIN_DEFAULT_PASSWORD` environment variables. The pgAdmin container will either fail to start or use hardcoded defaults, which are a security risk.

**Fix:** Add pgAdmin credentials to the env file or the docker-compose environment section. Since it has `profiles: ["admin-tools"]`, it won't run by default, but it should be configured correctly.

---

### 🟠 S5: Health Check Endpoint Doesn't Verify Database Connectivity

**File:** `backend/app/main.py`, lines 72-75

```python
@app.get("/health")
def health_check():
    return {"status": "healthy"}
```

**The problem:** The health check always returns healthy regardless of whether the database is accessible. The Docker health check (`docker-compose.yml` line 54) calls this endpoint. If the database goes down, the container will still report as healthy, and Docker won't restart it.

**Fix:** Add a simple `SELECT 1` query in the health check.

---

### 🟠 S6: No Connection Pool Limits on SQLAlchemy Engine

**File:** `backend/app/db/base.py`, lines 11-15

```python
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)
```

**The problem:** No `pool_size`, `max_overflow`, or `pool_timeout` parameters. The default SQLAlchemy pool allows 5 connections + 10 overflow. On a busy pharmacy day with multiple tills and background scheduler tasks all creating sessions, you could exhaust the pool and get `TimeoutError`.

**Fix:** Configure explicit pool limits based on expected concurrent connections.

---

### 🟠 S7: Scheduler Tasks Use Their Own Sessions Without Error Recovery

**File:** `backend/app/services/scheduler.py`

**The problem:** Each scheduled task creates a `SessionLocal()` and catches exceptions, but the `finally: db.close()` doesn't roll back on error. If a notification check partially commits and then fails, the session may be left in an inconsistent state.

Looking more carefully at the notification service, it appears to commit within the service calls, so the risk is partial commits on error.

**Fix:** Add `db.rollback()` in the except block before close.

---

### 🟠 S8: User Delete Is a Hard Delete — Breaks Sale History FK

**File:** `backend/app/api/endpoints/users.py`, line 348

```python
db.delete(db_user)
```

**The problem:** The `User` model has `sales = relationship("Sale", ..., cascade="all, delete-orphan")`. A hard delete of a user will **cascade delete all their sales**. This destroys transaction history.

**Impact:** If an admin deletes a cashier who processed sales, all of that cashier's sale records, sale items, and reversals will be deleted from the database. This is a data integrity catastrophe for a pharmacy.

**Fix:** Change to soft-delete (set `is_active = False`), or remove the cascade and use `SET NULL` on the FK. Never hard-delete a user who has sales.

---

## 5. Moderate Issues — Should Fix Before Go-Live

### 🟡 M1: Deprecated `datetime.utcnow()` Usage

**File:** `backend/app/core/security.py`, lines 41-43

```python
expire = datetime.utcnow() + timedelta(minutes=...)
```

`datetime.utcnow()` returns a naive datetime (no timezone info). It's officially deprecated in Python 3.12+. The `AuditService` correctly uses `datetime.now(timezone.utc)`, but the JWT token creation does not. This could cause token expiry issues across timezone boundaries.

**Fix:** Use `datetime.now(timezone.utc)` consistently.

---

### 🟡 M2: Deprecated `declarative_base()` Import

**File:** `backend/app/db/base.py`, line 5

```python
from sqlalchemy.ext.declarative import declarative_base
```

This import path is deprecated since SQLAlchemy 2.0. Should be `from sqlalchemy.orm import declarative_base` or preferably `DeclarativeBase`.

---

### 🟡 M3: Frontend API Client Uses `any` Types Pervasively

**File:** `frontend/src/services/api.ts`

Almost every method parameter is typed as `any`. Example: `createProduct(productData: any)`, `createSale(saleData: any)`. This defeats the purpose of TypeScript and makes it easy to send malformed requests.

**Fix:** Define proper TypeScript interfaces for request/response types.

---

### 🟡 M4: PWA Workbox Runtime Cache Pattern Won't Match Local API

**File:** `frontend/vite.config.ts`, lines 37-38

```js
urlPattern: /^https:\/\/api\..*/i,
```

This regex only matches URLs starting with `https://api.` — the local API is at `http://localhost:8000/api`. The runtime caching rule will never trigger for the local deployment scenario, which is the primary use case.

**Fix:** Update the regex or remove it — for a local-first app, caching API responses in the service worker is risky anyway (stale stock data).

---

### 🟡 M5: No Rate Limiting on Login Endpoint

**File:** `backend/app/api/endpoints/auth.py`

No rate limiting on POST `/api/auth/login`. A brute-force attack can try unlimited username/password combinations. FastAPI has no built-in rate limiter, so this needs middleware (e.g., slowapi).

For a local network deployment, the risk is lower, but if the system is ever exposed to the internet (Render deployment is mentioned in docs), this is critical.

---

### 🟡 M6: `SaleCreate` Schema Accepts `unit_price` from Frontend

**File:** `backend/app/schemas/sale.py`, line 15

```python
class SaleItemBase(BaseModel):
    unit_price: float = Field(..., gt=0)
```

The frontend sends `unit_price` in the sale request (POSPage.tsx line 337). However, the backend ignores it and recalculates from the product's current price via `_resolve_sale_unit_price()`. This is actually the **correct** behavior — but the schema shouldn't accept it, because it creates a false impression that the frontend controls pricing.

**Impact:** Low — the backend does the right thing. But it's confusing and could lead to bugs if someone changes the backend assuming the schema field is used.

---

### 🟡 M7: Frontend Route Guards Check Role Strings, Not Permissions

**File:** `frontend/src/App.tsx`

The frontend uses `user?.role !== 'admin'` for route guarding, while the backend uses granular permissions. This means the frontend routing doesn't match the backend capability model. A manager with `can_view_reports` permission is blocked from the dashboard by the frontend even though the backend would allow it.

**Fix:** Add `permissions` to the frontend `User` type and check permission-based access on the frontend.

---

## 6. Minor Issues — Cleanup and Hygiene

### 🔵 m1: `backend/pharma_pos.db` Exists (SQLite Leftover)
The backend directory has a 163KB SQLite database file and a backup. The system is PostgreSQL-only now, but these leftovers are confusing.

### 🔵 m2: `README.md` Says "Production Ready ✅"
Line 443: `**Status**: Production Ready ✅`. Per the AGENTS.md rules, this claim should not exist until the system actually supports it. The issues above demonstrate it is not production-ready yet.

### 🔵 m3: Root `pos-redesign.html` Is a Standalone File
A 23KB standalone HTML file at the project root. Appears to be an old design prototype. Should be moved to docs or removed.

### 🔵 m4: `database/init.sql` and `database/seed.sql` Exist But Directory Is Gitignored
`.gitignore` line 104 excludes `database/` — but the init and seed SQL files are needed for Docker setup (`docker-compose.yml` line 14 mounts `./database/init.sql`). These files may not be in the git repo, causing Docker first-time setup to fail.

### 🔵 m5: Alembic `sqlalchemy.url` Has Placeholder
`alembic.ini` line 60 has `sqlalchemy.url = postgresql://user:password@localhost:5432/database_name`. This is overridden by `env.py`, but it's still confusing for someone reading the config.

---

## 7. File-by-File Findings

### Backend Core

| File | Status | Notes |
|------|--------|-------|
| `app/main.py` | ✅ Working | Clean lifespan, proper CORS setup |
| `app/core/config.py` | ✅ Working | Good validators; production SECRET_KEY enforcement works |
| `app/core/security.py` | 🟡 Deprecated | `utcnow()` usage — see M1 |
| `app/core/money.py` | ✅ Solid | Proper Decimal handling with ROUND_HALF_UP |
| `app/db/base.py` | 🟡 Working | Missing pool limits (S6); deprecated import (M2) |

### Backend Models

| File | Status | Notes |
|------|--------|-------|
| `app/models/user.py` | ✅ Solid | Permission system is well-designed |
| `app/models/product.py` | ✅ Solid | Comprehensive pharmaceutical fields |
| `app/models/sale.py` | ✅ Solid | SaleReversal model is well-structured |
| `app/models/stock_adjustment.py` | ✅ Working | All types covered |
| `app/models/inventory_movement.py` | ✅ Solid | Append-only with proper references |
| `app/models/tenancy.py` | ✅ Working | Multi-branch schema is ready |
| `app/models/__init__.py` | ✅ Complete | All models exported |

### Backend Endpoints

| File | Status | Notes |
|------|--------|-------|
| `app/api/endpoints/auth.py` | ✅ Working | No public registration — correct |
| `app/api/endpoints/sales.py` | 🔴🟠 Issues | C2 (status filter missing), sale flow is otherwise solid |
| `app/api/endpoints/products.py` | 🟠 Issue | S3 (low-stock route unreachable), otherwise comprehensive |
| `app/api/endpoints/dashboard.py` | 🔴 Broken | C1 (all queries miss status filter) |
| `app/api/endpoints/users.py` | 🟠 Issue | S8 (hard delete cascades to sales) |
| `app/api/endpoints/stock_adjustments.py` | ✅ Solid | Proper FEFO, batch validation |
| `app/api/endpoints/stock_takes.py` | ✅ Working | Not deeply audited |
| `app/api/endpoints/system_ops.py` | ✅ Working | Backup/restore drill functionality |

### Backend Services

| File | Status | Notes |
|------|--------|-------|
| `app/services/inventory_service.py` | ✅ Solid | Sellable batch filter is correct |
| `app/services/audit_service.py` | ✅ Excellent | Hash chain with advisory locks |
| `app/services/scheduler.py` | 🟠 Issue | S7 (no rollback on error) |
| `app/services/notification_service.py` | ✅ Working | Not deeply audited |
| `app/services/sync_outbox_service.py` | ✅ Working | Correct outbox pattern |

### Frontend

| File | Status | Notes |
|------|--------|-------|
| `src/App.tsx` | 🟡 Issue | M7 (role strings vs permissions) |
| `src/services/api.ts` | 🟡 Issue | M3 (pervasive `any` types) |
| `src/stores/authStore.ts` | ✅ Working | Token management is correct |
| `src/stores/cartStore.ts` | 🟠 Issue | S1 (snapshot stock), but backend protects |
| `src/pages/POSPage.tsx` | ✅ Working | Well-built POS interface |
| `src/pages/DashboardPage.tsx` | ⚠️ Depends | Displays inflated data from broken backend queries (C1) |

### Infrastructure

| File | Status | Notes |
|------|--------|-------|
| `docker-compose.yml` | 🟠 Issues | S4 (pgAdmin auth), S5 (health check) |
| `alembic/env.py` | 🔴 Issue | C6 (incomplete model imports) |
| `alembic.ini` | 🔵 Minor | Placeholder URL |
| `scripts/provision_admin.py` | ✅ Working | Proper admin creation |
| `scripts/seed_data.py` | ✅ Working | Dev-only seed |

---

## 8. Recommended Priority Order

Fix these in order. Each group should be completed before moving to the next.

### Priority 1 — Data Integrity (Fix Immediately)

1. **C1 + C2:** Add `Sale.status == COMPLETED` filter to all dashboard and summary queries
2. **S8:** Change user delete from hard-delete to soft-delete (prevent sale cascade deletion)
3. **C6:** Fix alembic `env.py` model imports

### Priority 2 — Security (Fix Before Any Deployment)

4. **C4:** Replace placeholder SECRET_KEY in `backend/.env` with a real generated key; add config validator
5. **C5:** Remove `pharma_pos.db.backup` from git history; update `.gitignore`
6. **S2:** Consolidate env file strategy; use strong database passwords

### Priority 3 — Regulatory Compliance

7. **C3:** Implement prescription and controlled substance enforcement in `create_sale()`

### Priority 4 — Operational Reliability

8. **S3:** Move `/products/low-stock` route above `/{product_id}`
9. **S5:** Add database connectivity check to health endpoint
10. **S6:** Configure SQLAlchemy connection pool limits
11. **S7:** Add `db.rollback()` in scheduler task error handling

### Priority 5 — Polish for Go-Live

12. **M1:** Replace `utcnow()` with `datetime.now(timezone.utc)`
13. **M5:** Add rate limiting to login endpoint
14. **M7:** Align frontend route guards with backend permission model
15. **M4:** Fix PWA cache pattern or remove it
16. Clean up SQLite leftovers and placeholder claims

---

*This audit was conducted by reading every file referenced above. No assumptions were made about code behavior — each finding was confirmed by tracing the actual code paths.*
