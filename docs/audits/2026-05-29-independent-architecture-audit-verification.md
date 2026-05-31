# Independent Architecture Audit and Claude Verification

**Date:** 2026-05-29  
**Auditor:** Codex  
**Compared report:** `docs/audits/2026-05-29-comprehensive-architecture-audit.md`  
**Scope:** Source-code review of backend, frontend, migrations, deployment packaging, and targeted tests.  
**Verification run:** `python3 -m pytest backend/tests/test_app_mode.py backend/tests/test_customer_retention.py` -> 29 passed. `alembic heads` -> one head: `o5d6e7f8g9h0`.

## Executive Verdict

Claude's broad conclusion is correct: the local POS core is much stronger than the newer `online_pos` architecture, and `online_pos` should not be sold as production-ready yet.

However, Claude understated the main online risk. The issue is not only "no database RLS"; several live endpoints directly load and mutate rows by primary key without tenant checks. A malicious or buggy tenant user can reference another organization's IDs in POS, product, stock, user, sale, and dashboard workflows.

Claude also made several false or partially false claims:

- The customer-retention migration chain is not broken. It has the correct `down_revision`, and Alembic reports a single head.
- `/api/auth/heartbeat` is missing, but the frontend does not fall back to the product query on 404. It treats 404 as online because `404 < 500`.
- `backend/.dockerignore` does exclude `*.db`; it does not exclude `*.db.backup`.

## Independent Findings

### P0-01: `online_pos` Has Direct Tenant Bypasses In Operational Endpoints

**Status:** True and more severe than Claude reported.

The code scopes some list queries, but many direct object reads/writes are unscoped:

- `create_sale()` loads `Product` by `Product.id` only before dispensing stock (`backend/app/api/endpoints/sales.py:295`).
- Sale reversal loads `Sale` by id only (`sales.py:166`).
- `get_sale()` loads `Sale` by id only (`sales.py:773`).
- Product get/update/delete/batch/receive-stock paths load `Product` or `ProductBatch` by id only (`products.py:400`, `products.py:520`, `products.py:611`, `products.py:668`, `products.py:768`, `products.py:882`).
- Stock adjustment loads product/batch by id only (`stock_adjustments.py:114`, `stock_adjustments.py:123`).
- Dashboard endpoints aggregate all local tables with no `organization_id` filter (`dashboard.py:38-78`, `dashboard.py:112-129`, `dashboard.py:220-225`, `dashboard.py:517-530`).

Impact: in a shared cloud database, a crafted API request can read, reverse, adjust, or dispense another tenant's stock/sales if the caller can guess or learn IDs. Database RLS would help, but the application must also enforce object ownership consistently.

### P0-02: Online User Management Is Not Tenant-Scoped

**Status:** Skipped by Claude.

The `/users` endpoints are dangerous in `online_pos`:

- `list_users()` returns every user (`backend/app/api/endpoints/users.py:35`).
- `create_user()` does not stamp `organization_id` or `branch_id` from the current user (`users.py:90-98`).
- `update_user()` and `delete_user()` load target users by id only (`users.py:162`, `users.py:286`).
- Usernames/emails are globally unique (`backend/app/models/user.py:57-58`), which creates tenant collisions and makes per-pharmacy admin provisioning awkward.

Impact: an organization admin with user-management permission can see or modify users outside their organization, and newly created users may have no tenant scope.

### P0-03: Child Transaction Rows And Ledger Rows Are Not Tenant-Stamped

**Status:** Skipped by Claude.

`apply_tenant_scope()` stamps the `Sale` header, `Product`, and `StockAdjustment`, but not all child/ledger rows:

- `SaleItem` has nullable `organization_id` and `branch_id` columns (`backend/app/models/sale.py:118-119`) but `create_sale()` constructs sale items without setting them (`sales.py:461`).
- `ProductBatch` has nullable tenant columns (`backend/app/models/product.py:105-106`) but batch creation/receiving does not set them (`products.py:701-704`, `products.py:932-940`).
- `InventoryMovement` has nullable tenant columns (`backend/app/models/inventory_movement.py:34-36`) but `InventoryService.record_movement()` accepts no tenant arguments and writes none (`backend/app/services/inventory_service.py:47-73`).

Impact: reporting, audit reconstruction, and future tenant scoping become inconsistent because headers may be scoped while the operational detail rows remain null.

### P0-04: Sales Can Link A Customer From Another Organization

**Status:** Skipped by Claude.

`create_sale()` accepts `customer_id` from the request (`sales.py:430`) and later uses `db.get(CustomerModel, db_sale.customer_id)` (`sales.py:549`) without verifying `customer.organization_id == current_user.organization_id`.

Impact: a crafted sale can attach another tenant's customer, dispatch a receipt to that customer, and schedule follow-ups under the wrong customer record.

### P1-01: Categories And Suppliers Are Global Despite Online Tenant Use

**Status:** Skipped by Claude.

`Category` and `Supplier` have no tenant columns and globally unique names (`backend/app/models/category.py:17`, `backend/app/models/supplier.py:17`). Their endpoints list, create, update, and delete globally (`categories.py:26`, `categories.py:38`, `suppliers.py:28`, `suppliers.py:56`).

Impact: pharmacies in `online_pos` share supplier/category data and collide on common names. This may be an intentional shared catalog decision, but it is not documented or enforced as such.

### P1-02: Online Offline Queue Is Not A Recoverable Financial Ledger

**Status:** Claude true.

The queue is browser IndexedDB only (`frontend/src/services/offlineQueue.ts:17-19`). When offline, POS queues a sale and clears the cart (`frontend/src/pages/POSPage.tsx:340-363`) without generating a durable invoice number or confirmed receipt. Failed flushes are marked `failed` after three attempts (`offlineQueue.ts:160-167`) and the UI offers `Clear failed` (`frontend/src/components/layout/OfflineBanner.tsx:205-223`).

Impact: acceptable as a temporary "network drop buffer", not acceptable as a real offline financial ledger.

### P1-03: Frontend Heartbeat Contract Is Broken

**Status:** Claude identified the missing endpoint but described the behavior incorrectly.

`useOnlineStatus` calls `/api/auth/heartbeat` (`frontend/src/hooks/useOnlineStatus.ts:22`). No backend route exists. But the frontend returns `res.status < 500` (`useOnlineStatus.ts:41`), so a 404 is treated as online and the fallback product query is not used unless fetch throws.

Impact: the UI can report "online" when the intended heartbeat endpoint is missing. Add a real authenticated heartbeat endpoint or change the status check to require `2xx`.

### P1-04: Migration Chain Is Valid

**Status:** Claude false.

The customer-retention migration has `down_revision = 'n4c5d6e7f8g9'` (`backend/alembic/versions/o5d6e7f8g9h0_add_customer_retention_tables.py:17`). `alembic heads` reports exactly one head: `o5d6e7f8g9h0`. `alembic history --verbose` shows it directly follows the Telegram alert migration.

### P1-05: Docker Context Excludes `.db` But Not `.db.backup`

**Status:** Claude partially false.

The stale files exist locally:

- `backend/pharma_pos.db`
- `backend/pharma_pos.db.backup`

But `backend/.dockerignore` excludes `*.db` (`backend/.dockerignore:14-16`). It does not exclude `*.db.backup`, so only the backup file is likely included in the backend image context.

### P2 Findings Claude Got Mostly Right

- `updated_at` uses ORM `onupdate`, not server-side triggers (`product.py:93`, `user.py:67`, `customer.py:87`).
- `SaleItem.quantity` is integer-only (`backend/app/models/sale.py:133`).
- `_allocate_product_batches()` expands one object per unit before regrouping (`sales.py:79-81`, `sales.py:338-345`).
- Frontend auth token is stored in `localStorage` (`frontend/src/stores/authStore.ts:30-44`, `frontend/src/services/api.ts:46-49`).
- CORS allows all methods/headers (`backend/app/main.py:49-50`).
- There is no API version prefix; routes are mounted under `/api`.
- Login is the only endpoint with explicit rate limiting (`backend/app/api/endpoints/auth.py:22-48`).
- Scheduler jobs run in-process with the API and use `SessionLocal()` (`backend/app/services/scheduler.py:24-31`, `scheduler.py:201-417`).

## Claude Claim Verification

| Claude claim | Verdict | Notes |
|---|---|---|
| FEFO batch dispensing works with row locks | True | Core sale path locks product and batches and sorts FEFO. |
| Tamper-evident audit chain exists | True | `AuditService` hash chain and advisory lock are real. |
| Sales are transaction-safe | Mostly true | Strong for local POS; online tenant ownership is not safe. |
| Sync outbox pattern is solid | True for `local_pos` | It intentionally short-circuits in `online_pos`. |
| Permission model is granular | True | But user-management endpoints are not tenant-safe. |
| Login rate limiting exists | True | In-memory only, fine for local single process. |
| Secret key validation exists | True | Production placeholders/short secrets rejected. |
| C-01: No RLS / weak multi-tenancy | True, incomplete | Direct endpoint tenant bypasses are the bigger immediate issue. |
| C-02: Offline queue risks data loss | True | The queue is not a ledger. "Silent" is partly overstated because the UI shows failed counts. |
| C-03: Missing heartbeat causes product fallback every 15s | False mechanism | Endpoint is missing, but 404 is treated as online. |
| C-04: Customer migration chain may be broken | False | Single Alembic head and correct `down_revision`. |
| H-01: ORM-only `updated_at` | True | Direct SQL/bulk updates will not update it. |
| H-02: Missing composite indexes | Mostly true | `customers(organization_id, phone)` exists in migration, but many other composite indexes are absent. |
| H-03: Sync SQLAlchemy limits cloud concurrency | True as cloud concern | Local deployment impact is low. |
| H-04: Naive date windows | True | Several local/dashboard paths use naive `datetime.now()`. |
| H-05: No AI circuit breaker | True | Timeouts exist, no circuit breaker. |
| H-06: Customer analytics scans large tables | True | Summary aggregates broadly; acceptable only at small scale. |
| H-07: `.db` files ship in Docker image | Partially false | `*.db` excluded; `*.db.backup` is not. |
| H-08: In-process scheduler | True | Scheduler shares process and DB pool. |
| M-06: No DB retry means backend will crash on startup | Overstated | Engine creation is lazy; startup can succeed while health/endpoints fail. |
| M-08: PostgreSQL down gives unformatted tracebacks | Overstated | FastAPI usually returns generic 500 unless debug is enabled, but graceful error handling is still weak. |

## Claims Claude Skipped

1. Online POS direct object-access endpoints are not tenant-scoped, allowing cross-tenant sale/product/stock operations.
2. Online user administration can list/update/delete cross-tenant users and creates unscoped users.
3. Sale items, product batches, and inventory movements are not tenant-stamped in `online_pos`.
4. Sale customer linking does not validate customer ownership.
5. Local dashboard/reporting endpoints are unscoped in `online_pos`.
6. Categories and suppliers are global despite online POS exposing them as pharmacy-managed resources.
7. Customer routes are available in `local_pos` because `isPosMode` includes local mode, despite comments/docs saying customer retention is online-only (`frontend/src/App.tsx:142-170`).
8. Test coverage for the new `online_pos` tenant isolation is very thin; `test_app_mode.py` only checks mode helper behavior and write-guard routing.

## Recommended Fix Order

1. Freeze `online_pos` rollout until tenant isolation is fixed.
2. Add a reusable backend ownership helper for tenant-scoped row access, then apply it to sales, products, batches, stock adjustments, users, customers, and dashboard queries.
3. Stamp tenant IDs on all child rows and ledger rows (`SaleItem`, `ProductBatch`, `InventoryMovement`, `StockAdjustment`, audit log calls).
4. Decide whether categories/suppliers are shared master data or tenant-owned. Implement the schema accordingly.
5. Add PostgreSQL RLS or another database-level isolation mechanism after application-level ownership checks are corrected.
6. Replace the browser-only offline sale queue with a proper recoverable local ledger if `online_pos` must accept paid sales while offline.
7. Add `/api/auth/heartbeat` or make the frontend heartbeat require `2xx`.
8. Exclude `*.db.backup` from `backend/.dockerignore`.

