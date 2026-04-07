# Backend Audit Report

## Scope

Audit target: FastAPI backend for an offline-first pharmacy POS deployment.

Focus areas:
- security and access control
- data integrity and pharmacy-specific workflows
- offline deployment readiness
- operational maintainability and testability

Verification performed:
- source review across API, models, config, services, migrations, Docker artifacts, and setup scripts
- `python3 -m compileall backend/app` completed successfully
- no backend automated tests were found

## Executive Summary

Current backend quality is closer to an internal prototype than a production-ready pharmacy system.

The most serious blockers are:
- unauthenticated account registration with caller-controlled role assignment
- unsafe default SQLite configuration for the app's offline/local database mode
- sales logic that updates only aggregate stock and does not enforce batch-level depletion, FEFO, or prescription/controlled-drug rules
- absence of automated backend tests

Recommendation: do not market or deploy this backend to real pharmacies in its current form without a hardening phase.

## Rating

- Overall readiness: **High Risk**
- Market/deployment recommendation: **Not ready for real-world pharmacy rollout**

## Findings

### 1. Critical: Public user registration can create privileged accounts

Evidence:
- `backend/app/api/endpoints/auth.py:57-105`

Details:
- `/api/auth/register` is publicly exposed.
- The request model allows caller-supplied `role` and `is_active`.
- There is no dependency requiring an authenticated admin or manager.

Impact:
- Any unauthenticated user can create an active admin account.
- This is a full system compromise, not a minor auth issue.

Required action:
- Remove the public registration endpoint from production.
- Restrict user creation to authenticated admin flows only.
- Audit whether any deployed database already contains unauthorized users.

### 2. Critical: Default SQLite mode is not configured safely for FastAPI threading

Evidence:
- `backend/app/core/config.py:20-25`
- `backend/app/db/base.py:9-17`

Details:
- The default database URL is SQLite: `sqlite:///./pharma_pos.db`.
- `create_engine()` does not set SQLite-specific `connect_args={"check_same_thread": False}`.

Impact:
- For the offline install path, SQLite is the likely database engine.
- Under normal FastAPI request handling, SQLite may fail with thread-affinity errors or behave unpredictably in concurrent access scenarios.
- This is especially risky on busy tills with overlapping requests, scheduler activity, and local multi-user access.

Required action:
- Add proper SQLite engine configuration.
- Validate WAL mode, backup strategy, locking behavior, and corruption recovery for offline use.

### 3. High: Sales logic is not pharmacy-safe at batch level

Evidence:
- `backend/app/models/product.py:73-90`
- `backend/app/models/product.py:97-123`
- `backend/app/models/sale.py:101-118`
- `backend/app/api/endpoints/sales.py:69-145`
- `backend/app/api/endpoints/products.py:321-365`

Details:
- Inventory is decremented only from `Product.total_stock`.
- `SaleItem` has optional batch fields, but `create_sale()` never selects or stores a real batch.
- No FEFO logic exists.
- No batch quantity is reduced during sale creation.
- Product batch creation increases aggregate stock, but downstream sale flow never consumes it.

Impact:
- Expiry-aware dispensing is not reliable.
- Batch recall support is incomplete because sold items are not tied to actual dispensed batches.
- Aggregate stock can diverge from real batch stock.
- This is a major operational and regulatory problem for a pharmacy.

Required action:
- Implement batch reservation and depletion during sale processing.
- Enforce FEFO unless explicitly overridden with audit reason.
- Store dispensed batch number and expiry per sale line from actual stock movement.

### 4. High: Prescription and controlled-drug fields exist but are not enforced

Evidence:
- `backend/app/models/product.py:62-65`
- `backend/app/models/sale.py:58-72`
- `backend/app/api/endpoints/sales.py:69-145`

Details:
- The data model includes `prescription_status`, `is_narcotic`, `requires_id`, `customer_id_number`, `prescription_number`, `doctor_name`, and `has_prescription`.
- The sale creation path does not validate any of them.

Impact:
- A cashier can sell prescription-only or controlled products without required metadata or checks.
- This undermines the core reason to use pharmacy-specific software.

Required action:
- Add server-side sale validation rules by product type.
- Record override reason, operator, and timestamp for exceptional dispensing flows.

### 5. High: Invoice numbering and stock updates are race-prone

Evidence:
- `backend/app/api/endpoints/sales.py:25-42`
- `backend/app/api/endpoints/sales.py:111-145`

Details:
- Invoice numbers are generated from today's sale count.
- Two concurrent requests can produce the same invoice number.
- Stock checks and decrements are done in application code without explicit locking or retry strategy.

Impact:
- Duplicate invoice conflicts are possible.
- Concurrent sales can oversell stock.
- This matters in multi-terminal pharmacy environments.

Required action:
- Use a database-backed sequence or durable counter.
- Wrap sale creation in a transaction with appropriate locking semantics for the chosen database.

### 6. High: Production bootstrap artifacts include demo credentials and local database files

Evidence:
- `scripts/seed_data.py:28-67`
- `README.md` documents default credentials
- repository contains `.env`, `backend/.env`, `backend/pharma_pos.db`, `backend/pharma_pos.db.backup`, `frontend/.env.local`, and `pharma_pos.db`

Details:
- Seed data creates `admin/admin123`, `manager/manager123`, and `cashier/cashier123`.
- Local environment and database artifacts are present in the workspace.

Impact:
- This is acceptable for development but not for market distribution.
- It increases the chance of leaked secrets, reused demo passwords, and accidental shipment of real or sample data.

Required action:
- Strip demo credentials from production packaging.
- Generate first-run admin credentials at install time.
- Exclude all live database and env artifacts from shipped builds.

### 7. High: No automated backend tests were found

Evidence:
- `find backend -maxdepth 3 -type f \( -name 'test_*.py' -o -name '*_test.py' \)` returned no files

Impact:
- There is no regression safety net for auth, stock movement, pricing, or reporting.
- This is not acceptable for a pharmacy-facing transactional system.

Required action:
- Add unit, integration, and API tests before rollout.
- Cover auth, sales, stock mutation, role permissions, and batch expiry behavior first.

### 8. Medium: Session security depends on environment discipline and fails badly if `SECRET_KEY` is missing

Evidence:
- `backend/app/core/config.py:23-25`

Details:
- `SECRET_KEY` defaults to a randomly generated value at process startup.

Impact:
- If an installer or operator forgets to set `SECRET_KEY`, all JWTs become invalid after restart.
- This creates unstable authentication behavior in field deployments.

Required action:
- Fail fast on startup when `SECRET_KEY` is missing in production.
- Generate and persist it during installation, not at runtime.

### 9. Medium: Audit logging model exists but is not used in the write paths

Evidence:
- `backend/app/models/activity_log.py:11-27`
- no write-path usage was found in auth, product, user, supplier, or sales endpoints

Impact:
- There is no trustworthy audit trail for inventory changes, user changes, or dispensing actions.
- For pharmacies, that is a significant governance gap.

Required action:
- Log all security-sensitive and inventory-sensitive actions server-side.

### 10. Medium: Analytics and financial reporting are simplified and not defensible for real operations

Evidence:
- `backend/app/api/endpoints/dashboard.py:455-483`
- `backend/app/api/endpoints/dashboard.py:566-589`

Details:
- Profit is derived from current product cost, not immutable historical cost snapshots.
- Net profit is estimated using a hard-coded `15%` overhead rate.

Impact:
- Reported financial values can be materially misleading.
- This is acceptable for a demo dashboard, not for operational reporting.

Required action:
- Snapshot cost at sale time or use cost-of-goods logic from actual batches.
- Remove hard-coded pseudo-financial metrics unless they are clearly labeled as estimates.

## Offline Deployment Assessment

For an offline pharmacy deployment, the backend is directionally suitable only if treated as a local server appliance, not a cloud-connected app. The current implementation still needs major hardening:

- SQLite path needs production-safe configuration and recovery procedures.
- backup/restore workflow is not yet a controlled product feature
- no data repair tooling was found
- installer readiness is incomplete for safe first-run initialization
- no evidence of multi-terminal conflict handling was found

## Strengths

- Clear project structure and understandable FastAPI layering
- data model already includes useful pharmacy concepts such as batches, expiry, prescription flags, and notifications
- API organization is readable and maintainable
- background notification scheduling exists and is easy to reason about

## Recommended Release Gate

Minimum backend gate before selling to pharmacies:

1. remove public registration and harden user provisioning
2. fix SQLite/local deployment reliability
3. implement batch-aware stock movement with FEFO
4. enforce prescription and controlled-drug validation server-side
5. add transaction safety for invoice generation and stock mutation
6. add audit logs and backups
7. build automated test coverage for the critical flows

## Final Verdict

The backend is a good prototype foundation, but it is not yet safe enough for real pharmacy operations. The biggest issue is not code style; it is that the current system does not yet enforce the operational controls a pharmacy depends on.
