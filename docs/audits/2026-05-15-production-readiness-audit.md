# Pharma POS AI — Production Readiness Audit

**Date:** 2026-05-15
**Auditor:** Senior Systems Architect (Evidence-Based, Line-Level Review)
**Scope:** Full-stack file-by-file code review for 5-shop pharmacy rollout
**Previous audit:** `docs/audits/2026-05-01-deep-codebase-audit.md`

---

## Executive Summary

This audit is a brutally honest, evidence-based, line-by-line review of the Pharma POS AI codebase in its current state (commit `1f14b38`). It builds on the previous May 1st audit and evaluates what has been fixed, what remains broken, and what new risks have been introduced.

**Overall verdict: NOT READY for production go-live without addressing the Priority 1 findings below.**

The system has a strong architectural foundation — multi-tenant awareness, FEFO batch-based dispensing, append-only inventory movements, a tamper-evident audit chain, and well-structured sync outbox. However, several **data-integrity, regulatory-compliance, and security findings** remain unresolved from the previous audit and will cause financial or legal harm in production.

| Severity     | Count | Description                                       |
| ------------ | ----- | ------------------------------------------------- |
| 🔴 P1 Critical | 7     | Data loss, revenue misreporting, regulatory breach |
| 🟠 P2 High     | 6     | Operational risk, security weakness                |
| 🟡 P3 Medium   | 8     | Code quality, performance, maintainability         |
| 🔵 P4 Low      | 5     | Best practice, polish                              |

---

## 🔴 P1 — CRITICAL (Must Fix Before Go-Live)

### P1-01: User Deletion Destroys Sales History (DATA LOSS)

**File:** `backend/app/models/user.py`, line 70
**Code:**
```python
sales = relationship("Sale", back_populates="user", cascade="all, delete-orphan")
activity_logs = relationship("ActivityLog", back_populates="user", cascade="all, delete-orphan")
```

**Impact:** `DELETE /users/{user_id}` in `users.py` (line 348) calls `db.delete(db_user)`. SQLAlchemy's `cascade="all, delete-orphan"` on both `sales` and `activity_logs` means deleting a user **permanently destroys all of their sales records AND audit trail entries**. In a pharmacy serving five shops, this is catastrophic:
- Financial records disappear (tax audit failure)
- The tamper-evident hash chain in the audit log is broken (entries removed mid-chain)
- Past prescriptions dispensed by that user are gone

**Fix:** Implement soft-delete (set `is_active=False`, clear credentials). Change cascade to `cascade="save-update, merge"` and add `passive_deletes=True`. Block hard delete at the endpoint level.

---

### P1-02: Dashboard Revenue Includes Voided/Refunded Sales (FINANCIAL MISREPORTING)

**File:** `backend/app/api/endpoints/dashboard.py`, lines 38-603
**File:** `backend/app/api/endpoints/sales.py`, lines 526-571

**Evidence:** Every dashboard KPI query operates on the entire `Sale` table without filtering by `Sale.status`. The `get_dashboard_kpis`, `get_sales_trend`, `get_staff_performance`, `get_revenue_analysis`, and `get_financial_kpis` endpoints all use:
```python
db.query(func.sum(Sale.total_amount))  # No .filter(Sale.status == SaleStatus.COMPLETED)
```
Similarly, `get_today_sales_summary()` in `sales.py` (line 526+) sums revenue without status filters.

**Impact:** Managers will see inflated revenue including voided and refunded transactions. This produces incorrect daily closeouts, KPIs, and staff performance metrics. For a pharmacy handling controlled substances, revenue discrepancies trigger regulatory scrutiny.

**Fix:** Add `.filter(Sale.status == SaleStatus.COMPLETED)` to every aggregation query. The `EndOfDayCloseout` schema already has fields for `completed_revenue`, `refunded_revenue`, `cancelled_revenue` — the closeout endpoint at line 584+ correctly separates them, but the other 10+ dashboard queries do not.

---

### P1-03: No Server-Side Prescription/Narcotic Enforcement (REGULATORY BREACH)

**File:** `backend/app/api/endpoints/sales.py`, `create_sale()` (lines 264-488)
**File:** `backend/app/models/product.py` — `prescription_status` field (line 41), `is_narcotic` field (line 42)

**Evidence:** The `Product` model has fields:
```python
prescription_status = Column(SQLEnum(PrescriptionStatus), ...)  # OTC/PRESCRIPTION_ONLY/CONTROLLED
is_narcotic = Column(Boolean, default=False)
```
But `create_sale()` performs **zero** server-side checks on these fields. A cashier can sell a prescription-only or controlled substance without any validation. The `has_prescription` field exists in `SaleCreate` schema (line 67 of `schemas/sale.py`) but is never enforced.

**Impact:** This is a pharmaceutical compliance violation in any jurisdiction. Dispensing prescription-only or controlled drugs without validation is a legal liability that could shut down the entire operation.

**Fix:** In `create_sale()`, before processing each item:
1. If `product.prescription_status == PrescriptionStatus.PRESCRIPTION_ONLY`, require `sale_data.has_prescription == True` and `sale_data.prescription_number` to be non-empty
2. If `product.is_narcotic == True`, require prescription validation AND restrict to users with explicit permission
3. Log controlled substance dispensing in the audit trail with prescription details

---

### P1-04: Alembic Model Imports Are Incomplete (MIGRATION RISK)

**File:** `backend/alembic/env.py`, lines 17-29

**Evidence:** The import block explicitly imports only 10 models:
```python
from app.models import (
    User, Category, Supplier, Product, ProductBatch,
    Sale, SaleItem, Notification, ActivityLog,
    RestoreDrill, StockAdjustment,
)
```
But `backend/app/models/__init__.py` exports **25 models** including: `SaleReversal`, `InventoryMovement`, `StockTake`, `StockTakeItem`, `SyncEvent`, `SyncEventCounter`, `IngestedSyncEvent`, `Organization`, `Branch`, `Device`, `AIWeeklyManagerReport`, `AIWeeklyReportDelivery`, `AIWeeklyReportDeliverySetting`, `AIExternalProviderSetting`, `CloudSaleFact`, `CloudInventoryMovementFact`, `CloudProductSnapshot`, `CloudBatchSnapshot`, `CloudReconciliationAcknowledgement`.

**Impact:** Running `alembic revision --autogenerate` will see the missing tables as "not in metadata" and generate DROP TABLE statements for 15+ tables. A single careless migration run wipes cloud reporting data, sync events, inventory movements, tenancy tables, and AI reports.

**Fix:** Replace the explicit import list with:
```python
from app.models import *  # noqa: F403
```
Or import all 25 models explicitly. Then add a safety check: `assert len(Base.metadata.tables) >= 25`.

---

### P1-05: SECRET_KEY Is a Placeholder in Committed .env (AUTH BYPASS)

**File:** `backend/.env`, line 13
```
SECRET_KEY=replace-with-generated-secret-key
```

**Evidence:** This file is not git-tracked (`.gitignore` line 40 excludes `.env`), but it exists on disk with a predictable placeholder. If the deployment uses this value, any attacker can forge JWT tokens because the key is a static, publicly known string. The root `.env` has a proper 64-hex-char key on line 20, but this creates confusion about which file takes precedence.

**Dual .env conflict:** `backend/.env` (line 3) sets `DATABASE_URL=postgresql://pharma_user:newpassword123@localhost:5432/pharma_pos` while the root `.env` (line 8) sets `DATABASE_URL=` (empty). Docker Compose uses `env_file: ./backend/.env` (docker-compose.yml line 8). This means the password `newpassword123` is the production database credential.

**Fix:**
1. Enforce key strength at startup in `config.py` — if `len(SECRET_KEY) < 32` or key matches known placeholder, refuse to start in production mode
2. Remove `backend/.env` from the repository working tree and document that operators must create it from a template
3. Change the default database password

---

### P1-06: `GET /products/low-stock` Route Is Unreachable (BROKEN FEATURE)

**File:** `backend/app/api/endpoints/products.py`

**Evidence from grep:** Route definitions in order:
- Line 225: `@router.get("")`
- Line 262: `@router.get("/catalog")`
- Line 305: `@router.get("/search")`
- Line 339: `@router.get("/{product_id}")` ← **Catch-all path parameter**
- Line 980: `@router.get("/low-stock")` ← **Defined AFTER catch-all**

FastAPI processes routes in definition order. A request to `GET /products/low-stock` matches `/{product_id}` with `product_id="low-stock"`, which then fails with a 422 validation error (not an integer) or returns a confusing "Product not found".

**Impact:** The frontend's `getLowStockProducts()` call (`api.ts` line 137) silently fails. Pharmacy staff never see low-stock alerts in the product management view.

**Fix:** Move the `@router.get("/low-stock")` definition BEFORE `@router.get("/{product_id}")`.

---

### P1-07: No Rate Limiting on Login Endpoint (BRUTE FORCE VULNERABILITY)

**File:** `backend/app/api/endpoints/auth.py`, lines 17-56

**Evidence:** The `POST /auth/login` endpoint has no rate limiting, account lockout, or failed-attempt tracking. An attacker can make unlimited login attempts per second.

**Impact:** With a five-shop deployment and pharmacy workstations exposed on local networks, this enables brute-force credential attacks. The weak default password pattern (`newpassword123` in `.env`) compounds this risk.

**Fix:** Add `slowapi` or a custom rate limiter: max 5 failed attempts per username per 5 minutes. Log failed login attempts via `AuditService.log()`.

---

## 🟠 P2 — HIGH (Fix Before or Immediately After Go-Live)

### P2-01: Health Check Is Superficial

**File:** `backend/app/main.py`

The `/health` endpoint returns a static `"healthy"` response without checking database connectivity. Docker Compose relies on this for orchestration (docker-compose.yml line 54). The `_database_connected()` function exists in `system_ops.py` (line 157) but is not used in the health check.

**Fix:** Make `/health` call `engine.connect()` + `SELECT 1` and return unhealthy if the database is unreachable.

---

### P2-02: No Connection Pool Limits

**File:** `backend/app/db/base.py`

The SQLAlchemy engine is created without explicit `pool_size`, `max_overflow`, or `pool_recycle` settings. Under concurrent till usage across 5 shops, this defaults to 5 connections with 10 overflow — too few for peak pharmacy hours.

**Fix:** Configure `pool_size=10, max_overflow=20, pool_recycle=1800` based on shop count and concurrency expectations.

---

### P2-03: PWA Service Worker Caches API Responses Incorrectly

**File:** `frontend/vite.config.ts`, lines 36-49

```javascript
runtimeCaching: [{
    urlPattern: /^https:\/\/api\..*/i,
    handler: 'NetworkFirst',
    ...
}]
```

This regex pattern matches `https://api.*` but the actual API is served from `/api` (relative path) or `http://localhost:8000/api`. The regex will **never match** the actual API URLs, meaning API caching is silently non-functional. This makes the PWA's offline claim hollow.

Additionally, caching API responses for 24 hours (`maxAgeSeconds: 60 * 60 * 24`) for a real-time POS system is dangerous — stale stock quantities could allow overselling.

**Fix:** Either remove the runtime caching (since the app requires a running local backend per AGENTS.md) or adjust the URL pattern and reduce TTL dramatically for stock-sensitive endpoints.

---

### P2-04: Frontend Cart Validates Against Stale Stock

**File:** `frontend/src/stores/cartStore.ts`, lines 85-86, 102-103, 127-128

```typescript
if (newQuantity > product.total_stock) {
    throw new Error('Insufficient stock')
}
```

The cart checks `product.total_stock` from when the product was loaded into the UI. Between loading and checkout, another till could have sold the same stock. The server-side `with_for_update()` in `create_sale()` correctly handles this, but the frontend gives a false sense of security. If server rejects the sale, the user gets a generic error.

**Fix:** Display a clear "Stock changed — please review your cart" message when the server rejects. Consider adding a pre-checkout stock validation API call.

---

### P2-05: AI Insights Service Ignores Sale Status

**File:** `backend/app/services/ai_insights.py`, lines 38-42, 85-90

```python
products_with_sales = db.query(SaleItem.product_id).join(
    Sale, Sale.id == SaleItem.sale_id
).filter(
    Sale.created_at >= start_date
).distinct().all()
```

Dead stock detection and reorder suggestions count all sales regardless of status. A voided sale still counts as "recent activity," masking genuinely dead stock. The same issue affects `suggest_reorder_quantity()` and `analyze_sales_pattern()`.

**Fix:** Add `.filter(Sale.status == SaleStatus.COMPLETED)` to all queries in `AIInsightsService`.

---

### P2-06: Notification Service Uses `datetime.now()` Without Timezone

**File:** `backend/app/services/notification_service.py`, lines 114, 153, 189, 223, 250, 271, 309

All duplicate-check queries use `datetime.now()` without timezone awareness:
```python
Notification.created_at >= datetime.now() - timedelta(days=1)
```

Since `ActivityLog.created_at` and `Notification.created_at` use `DateTime(timezone=True)` with `server_default=func.now()`, comparing against naive `datetime.now()` will cause timezone-dependent behavior. In the `Africa/Accra` timezone this is UTC+0 so it works by accident, but moving to any offset timezone breaks deduplication.

**Fix:** Use `datetime.now(timezone.utc)` consistently.

---

## 🟡 P3 — MEDIUM (Address in Production Hardening Phase)

### P3-01: `auth.py` Login Endpoint Leaks Timing Information

**File:** `backend/app/api/endpoints/auth.py`, line 40

```python
user = db.query(User).filter(User.username == normalized_username).first()
if not user or not verify_password(form_data.password, user.hashed_password):
```

When the user doesn't exist, `verify_password` is never called. The response time difference between "user not found" (fast) and "wrong password" (slow bcrypt hash) reveals whether a username exists. This is a username enumeration vulnerability.

**Fix:** Always run `verify_password` against a dummy hash when the user is not found.

---

### P3-02: Duplicate Role Check Functions

**File:** `backend/app/api/endpoints/users.py`, lines 20-59

`require_admin()` and `require_admin_or_manager()` are defined locally in `users.py`, duplicating the centralized `require_admin` and `require_manager` dependencies in `api/dependencies/auth.py` (lines 121-122). The `users.py` versions are NOT used by any endpoint in that file — the actual endpoint functions use `require_manage_users` from the centralized dependencies.

**Impact:** Dead code that confuses future maintainers.

**Fix:** Remove the unused local functions.

---

### P3-03: Cart Store Allows Negative Total Prices

**File:** `frontend/src/stores/cartStore.ts`, line 67, 96, 150

```typescript
total_price: unitPrice * item.quantity - item.discount_amount
```

If `discount_amount > unitPrice * quantity`, the total price goes negative. There's no guard against this.

**Fix:** Add `Math.max(0, ...)` or validate discount doesn't exceed subtotal.

---

### P3-04: `create_sale()` Missing Key Schema Fields

**File:** `backend/app/api/endpoints/sales.py`, lines 380-394

The `Sale` object creation does not populate several fields from `SaleCreate`:
- `customer_id_number`, `customer_address`
- `momo_reference`, `momo_number`
- `prescription_number`, `doctor_name`, `has_prescription`
- `insurance_company`, `insurance_claim_number`, `insurance_coverage`
- `status` (defaults to model default, but should explicitly set `SaleStatus.COMPLETED`)

The frontend sends these fields, but the backend silently ignores them.

**Fix:** Map all SaleCreate fields to the Sale model constructor.

---

### P3-05: Scheduler Tasks Swallow Exceptions

**File:** `backend/app/services/scheduler.py`, all static task methods

Every scheduler task catches `Exception` and only logs it:
```python
except Exception as e:
    logger.error(f"Error in expiry check task: {str(e)}")
```

Stack traces are lost. If the database connection pool is exhausted or a migration broke a table, the scheduler silently fails forever with minimal diagnostic information.

**Fix:** Log the full traceback: `logger.exception(...)` instead of `logger.error(f"...{str(e)}")`.

---

### P3-06: `_allocate_product_batches` Memory Allocation Pattern

**File:** `backend/app/api/endpoints/sales.py`, lines 55-91

```python
allocated_batches.extend([batch] * take_quantity)
```

For a sale of 500 units from one batch, this creates a list of 500 references to the same batch object. While it's later consolidated back into per-batch quantities (lines 319-325), this is wasteful. For high-volume wholesale orders, this could briefly allocate significant memory.

**Fix:** Return `[(batch, take_quantity)]` tuples directly instead of the expand-and-consolidate pattern.

---

### P3-07: No CSRF Protection for Cookie-Based Auth Fallback

The API uses Bearer token auth, which is inherently CSRF-safe. However, the CORS configuration in `main.py` allows `http://localhost:*` origins and `allow_credentials=True`. If any future cookie-based authentication is added, this configuration would be CSRF-vulnerable.

**Fix:** Document that cookie-based auth should never be added without CSRF tokens.

---

### P3-08: Frontend Uses `any` Type Pervasively

**File:** `frontend/src/services/api.ts`

Nearly every method parameter and several return types use `any`:
```typescript
async createProduct(productData: any) { ... }
async createSale(saleData: any) { ... }
async getProducts(params?: any) { ... }
```

This eliminates TypeScript's type safety guarantees for the entire API surface.

**Fix:** Define proper interfaces for all request/response types matching the Pydantic schemas.

---

## 🔵 P4 — LOW (Best Practice Improvements)

### P4-01: `.gitignore` Excludes All `.md` Files

**File:** `.gitignore`, line 94
```
*.md
```

This blanket exclusion with selective re-includes (`!README.md`, `!AGENTS.md`, `!docs/`) means any markdown documentation placed outside `docs/` is silently untracked. New audit reports or architecture docs at project root would be lost.

---

### P4-02: Docker Backend Health Check Uses `python -c "import requests"`

**File:** `docker-compose.yml`, line 54
```yaml
test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/health')"]
```

The `requests` library may not be in the container. The backend uses `httpx`, not `requests`. Use `curl` or `httpx` instead.

---

### P4-03: `security.py` Uses Deprecated `datetime.utcnow()`

**File:** `backend/app/core/security.py`

`datetime.utcnow()` returns a naive datetime. The rest of the codebase correctly uses `datetime.now(timezone.utc)`. This inconsistency could cause JWT expiry issues in non-UTC environments.

---

### P4-04: Frontend Fallback Loading State Is Minimal

**File:** `frontend/src/App.tsx`, line 82
```tsx
<Suspense fallback={<div className="p-6 text-sm text-gray-500">Loading...</div>}>
```

For a POS system, startup speed matters. The fallback should be a proper skeleton screen or branded loader, not a plain text div.

---

### P4-05: Batch `received_date` Has No Default

**File:** `backend/app/models/product.py`

The `ProductBatch.received_date` column uses `server_default=func.now()`, but the `ProductBatch()` constructor in `receive_stock()` doesn't explicitly set it. It relies on the database default, which works for inserts but not for in-memory calculations before commit.

---

## Architectural Strengths (Acknowledged)

The codebase has significant architectural merit that the previous audit may have underemphasized:

1. **Tamper-evident audit chain** (`AuditService`): SHA-256 hash chain with advisory locking is production-grade for pharmacy regulatory compliance. The `verify_integrity()` method is well-implemented.

2. **FEFO batch allocation** (`_allocate_product_batches`): Correctly sorts by `expiry_date ASC, received_date ASC, id ASC` with `with_for_update()` row locking. This is genuinely correct pharmacy dispensing behavior.

3. **Sync outbox pattern** (`SyncOutboxService`): Uses monotonic sequence numbers, payload hashing, and UUID event IDs. The ingestion endpoint is properly idempotent with duplicate detection. This is a solid foundation for offline-first operation.

4. **Permission system**: Granular permissions with role defaults and per-user overrides. The `effective_permissions` property pattern is clean and extensible.

5. **AI safety boundaries**: The `AIManagerService` correctly refuses clinical/dispensing requests, operates on read-only projections, and falls back to deterministic answers when the LLM is unavailable. This is the right design for a pharmacy context.

6. **Inventory movement ledger**: Append-only `InventoryMovement` with movement types, source document linking, and `stock_after` snapshots. This provides a complete audit trail for stock changes.

7. **Backup and restore drill system** (`system_ops.py`): The `RestoreDrill` model and checklist approach is unusual and commendable for a pharmacy system.

---

## Remediation Priority Matrix

| Priority | Finding | Effort | Risk if Ignored |
| -------- | ------- | ------ | --------------- |
| 🔴 P1-01 | User deletion cascades | 2h | Data destruction |
| 🔴 P1-02 | Revenue misreporting | 3h | Financial audit failure |
| 🔴 P1-03 | No prescription enforcement | 4h | Regulatory shutdown |
| 🔴 P1-04 | Alembic imports incomplete | 30m | Table loss on migration |
| 🔴 P1-05 | Weak SECRET_KEY | 1h | JWT forgery |
| 🔴 P1-06 | Low-stock route unreachable | 15m | Broken feature |
| 🔴 P1-07 | No login rate limiting | 2h | Brute force attack |
| 🟠 P2-01 | Superficial health check | 30m | Silent DB failure |
| 🟠 P2-02 | No pool limits | 15m | Connection exhaustion |
| 🟠 P2-03 | PWA cache misconfigured | 1h | False offline claim |
| 🟠 P2-04 | Stale cart stock | 1h | Confusing UX |
| 🟠 P2-05 | AI insights ignores status | 1h | Bad recommendations |
| 🟠 P2-06 | Naive datetime in notifications | 30m | Duplicate alerts |

**Estimated total remediation: ~17 hours for all P1+P2 findings.**

---

## Delta from Previous Audit (May 1, 2026)

| Previous Finding | Status |
| ---------------- | ------ |
| Dashboard revenue includes cancelled sales | ❌ **Still open** (P1-02) |
| User deletion cascades | ❌ **Still open** (P1-01) |
| Alembic imports incomplete | ❌ **Still open** (P1-04) |
| SECRET_KEY placeholder | ❌ **Still open** (P1-05) |
| Low-stock route unreachable | ❌ **Still open** (P1-06) |
| No prescription enforcement | ❌ **Still open** (P1-03) |
| Superficial health check | ❌ **Still open** (P2-01) |
| No connection pool limits | ❌ **Still open** (P2-02) |
| `pharma_pos.db.backup` in git | ✅ **Fixed** (commit `1f14b38`) |
| `.gitignore` updated for `.db.backup` | ✅ **Fixed** (line 34) |

**Conclusion:** 8 of 10 previous critical/high findings remain unresolved. The only fix applied since the last audit was removing the backup database file from git tracking.

---

## Verdict

This system has a **strong architectural foundation** — the audit chain, FEFO dispensing, sync outbox, and permission model are genuinely well-designed for pharmacy operations. However, the 7 critical findings (especially P1-01, P1-02, and P1-03) make it **unsafe for a 5-shop production deployment** in its current state.

**Minimum requirements for go-live:**
1. Fix all P1 findings (~13 hours)
2. Fix P2-01 and P2-02 (~45 minutes)
3. Run the test suite and verify no regressions
4. Rotate the SECRET_KEY and database passwords on all deployment targets
5. Execute one restore drill and record it via the system

The remaining P2-P4 findings should be addressed in the first production hardening sprint.
