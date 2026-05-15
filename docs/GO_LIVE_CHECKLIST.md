# Go-Live Checklist — 5-Shop Pharmacy Rollout

> **Last updated:** 2026-05-15 20:24 UTC
> **Source audits:** `docs/audits/2026-05-15-production-readiness-audit.md`, `docs/audits/2026-05-15-production-readiness-audit-v2.md`
> **Status:** 🟡 **CONDITIONALLY READY** — All critical code defects resolved. Operational verification and credential rotation remain.

---

## ⚠️ MANDATORY UPDATE RULE

> **Every time you check off, modify, or add an item in this checklist, you MUST include the date and time (UTC) of the change.**
> Format: `YYYY-MM-DD HH:MM UTC`
>
> Examples:
> - `[x] Item description ✅ *(2026-05-15 20:15 UTC)*`
> - `[/] Partially done *(started 2026-05-15, pending verification)*`
> - `[ ] Not started`
>
> This ensures full traceability for regulatory and operational audit purposes.

---

## How to Read This Checklist

- `[x]` — Completed and verified in codebase
- `[/]` — Partially done or has known residual items
- `[ ]` — Not started or not verified
- **Audit ref** links each item to the specific audit finding
- **Date** in parentheses shows when the item was resolved

---

## Phase 0: Critical Audit Findings (All Resolved ✅)

> These are the critical findings from both production readiness audits.
> All code-level defects have been remediated.

### Data Integrity

- [x] **P1-01:** User deletion uses soft-delete instead of hard-delete ✅ *(2026-05-15 19:44 UTC)*
  - Fixed: `cascade="save-update, merge"` + `passive_deletes=True` on `User.sales` and `User.activity_logs`
  - Fixed: `users.py` delete endpoint sets `is_active=False` and clears password
  - Files: `backend/app/models/user.py`, `backend/app/api/endpoints/users.py`

- [x] **P1-02:** Dashboard/KPI queries filter by `Sale.status == COMPLETED` ✅ *(2026-05-15 19:45 UTC)*
  - Fixed: All 14+ dashboard queries now include `.filter(Sale.status == SaleStatus.COMPLETED)`
  - Fixed: Today's sales summary in `sales.py` also filtered
  - Files: `backend/app/api/endpoints/dashboard.py`, `backend/app/api/endpoints/sales.py`

- [x] **V2-P1-01:** Backend rejects negative sale totals from excessive discounts ✅ *(2026-05-15 19:45 UTC)*
  - Fixed: Item-level discount capped at line subtotal, sale-level discount capped at subtotal
  - Fixed: Final `total_amount < 0` check added as backstop
  - File: `backend/app/api/endpoints/sales.py`

### Regulatory Compliance

- [x] **P1-03:** Server-side prescription and narcotic enforcement in `create_sale()` ✅ *(2026-05-15 19:45 UTC)*
  - Fixed: `PRESCRIPTION_REQUIRED` products require `has_prescription=True` + prescription number
  - Fixed: Narcotic products require prescription + customer name
  - Fixed: `requires_id` products require customer ID number
  - Fixed: All schema fields now mapped to Sale constructor
  - File: `backend/app/api/endpoints/sales.py`

### Database Safety

- [x] **P1-04:** Alembic `env.py` imports all models correctly ✅ *(2026-05-15 19:30 UTC — verified, no fix needed)*
  - Verified: `models/__init__.py` imports all 30 tables via package-level imports
  - Importing `from app.models import (...)` triggers `__init__.py`, populating `Base.metadata`
  - This was a false alarm from Audit V1, correctly rejected by Audit V2

### Security

- [x] **P1-05:** SECRET_KEY enforced as strong key at startup ✅ *(2026-05-15 19:46 UTC)*
  - Fixed: Rejects known placeholders (`changeme`, `replace-with-generated-secret-key`, etc.)
  - Fixed: Rejects keys shorter than 32 characters in production
  - Fixed: Warns in development mode
  - File: `backend/app/core/config.py`

- [x] **P1-07:** Rate limiting on login endpoint ✅ *(2026-05-15 19:46 UTC)*
  - Fixed: 5 attempts per 5 minutes per username (in-memory, suitable for single-process local deployment)
  - Fixed: Constant-time response via dummy bcrypt hash when user not found (P3-01 timing fix)
  - File: `backend/app/api/endpoints/auth.py`

### Broken Features

- [x] **P1-06:** `/products/low-stock` route defined before `/{product_id}` catch-all ✅ *(2026-05-15 19:47 UTC)*
  - Fixed: Moved `@router.get("/low-stock")` before `@router.get("/{product_id}")`
  - File: `backend/app/api/endpoints/products.py`

---

## Phase 1: Operational Blockers

### Backup & Recovery

- [x] Backup scripts exist for Windows and Linux *(pre-2026-05-15)*
- [x] Restore script exists *(pre-2026-05-15)*
- [x] Backup task installer exists for both platforms *(pre-2026-05-15)*
- [x] Restore drill tracking system implemented *(pre-2026-05-15)*
- [ ] Nightly database backups are automated on every client machine
- [ ] Backup retention is configured and verified
- [ ] Restore procedure has been tested on a real backup file
- [x] Backup status API available for monitoring *(pre-2026-05-15)*

### Deployment & Startup

- [x] Docker Compose stack defined and working *(pre-2026-05-15)*
- [x] PostgreSQL health check configured *(pre-2026-05-15)*
- [x] Backend health check verifies DB connectivity ✅ *(2026-05-15 19:47 UTC — was P2-01)*
  - Fixed: `/health` now executes `SELECT 1` against DB, returns 503 if disconnected
  - File: `backend/app/main.py`
- [x] Backend configured to start automatically *(pre-2026-05-15)*
- [x] Frontend configured to start automatically *(pre-2026-05-15)*
- [ ] Local PostgreSQL service start-on-boot verified on target machines
- [x] Environment setup scripts exist *(pre-2026-05-15)*

### Credentials & Secrets

- [x] `.env` files excluded from git *(pre-2026-05-15)*
- [x] Database files excluded from git *(pre-2026-05-15)*
- [x] Database backup removed from git history *(2026-05-15 — commit 1f14b38)*
- [/] Runtime `.env`, `.db`, and backup artifacts excluded from packaged releases *(needs installer verification)*
- [ ] Demo credentials removed from release-facing login and install materials
- [ ] SECRET_KEY rotated and strong on all deployment targets
- [ ] Database password changed from default `newpassword123`

### Operational Workflows

- [x] End-of-day closeout endpoint implemented *(pre-2026-05-15)*
- [x] Sale void and refund workflows implemented with stock restoration *(pre-2026-05-15)*
- [x] Void/refund requires permission *(pre-2026-05-15)*
- [ ] End-of-day closeout reviewed in pilot operations
- [ ] Sale void/refund control verified in pilot operations
- [x] System diagnostics endpoint available *(pre-2026-05-15)*
- [ ] A support technician can verify system health in under 5 minutes

---

## Phase 2: Data Integrity & Traceability

### Audit Trail

- [x] Tamper-evident audit logging implemented *(pre-2026-05-15)*
- [x] Sale creation emits audit records *(pre-2026-05-15)*
- [x] Sale void/refund emits audit records *(pre-2026-05-15)*
- [x] Stock receipt emits audit records *(pre-2026-05-15)*
- [x] Stock adjustment emits audit records *(pre-2026-05-15)*
- [x] User management actions emit audit records *(pre-2026-05-15)*
- [x] Product master-data changes emit audit records *(pre-2026-05-15)*
- [x] Audit log viewer available in UI *(pre-2026-05-15)*
- [x] Audit log CSV export available *(pre-2026-05-15)*
- [x] Audit integrity verification endpoint *(pre-2026-05-15)*

### Inventory Tracking

- [x] Append-only inventory movement ledger implemented *(pre-2026-05-15)*
- [x] Every stock change records a movement entry *(pre-2026-05-15)*
- [x] `stock_after` snapshot recorded on every movement *(pre-2026-05-15)*
- [x] Source document linking (type + ID) on every movement *(pre-2026-05-15)*

### Sync & Cloud

- [x] Sync outbox pattern implemented with monotonic sequences *(pre-2026-05-15)*
- [x] Payload hashing for deduplication *(pre-2026-05-15)*
- [x] Idempotent sync ingestion endpoint *(pre-2026-05-15)*
- [x] Cloud projection into reporting tables *(pre-2026-05-15)*
- [x] Cloud reconciliation service *(pre-2026-05-15)*

### Test Coverage

- [/] Frontend test files exist for key pages — 21 tests passing *(2026-05-15 20:16 UTC)*
- [x] Backend tests pass — 97/99, 2 pre-existing unrelated failures in AI weekly report retry *(2026-05-15 20:14 UTC)*
- [ ] Sales flow has regression coverage (backend)
- [ ] Sale void/refund flow has regression coverage (backend)
- [ ] Dashboard financial endpoint stability has regression coverage (backend)

---

## Phase 3: Workflow Stability

### POS Workflow

- [x] POS page implemented as primary route *(pre-2026-05-15)*
- [x] Product search implemented *(pre-2026-05-15)*
- [x] Cart with retail/wholesale pricing modes *(pre-2026-05-15)*
- [x] Cart prevents negative line totals ✅ *(2026-05-15 19:49 UTC — P3-03)*
  - Fixed: `updateDiscount` caps at line subtotal, `Math.max(0, ...)` guard
  - File: `frontend/src/stores/cartStore.ts`
- [x] FEFO batch allocation during sales *(pre-2026-05-15)*
- [x] Multiple payment methods supported *(pre-2026-05-15)*
- [x] Cashier login lands in correct route *(pre-2026-05-15)*
- [ ] POS workflow stable on common pharmacy workstation screen sizes
- [ ] Receipt printing verified with target printers
- [ ] Barcode scanner input path verified

### Dashboard & Reporting

- [x] Local dashboard with KPIs *(pre-2026-05-15)*
- [x] Cloud reporting dashboard *(pre-2026-05-15)*
- [x] AI weekly manager reports *(pre-2026-05-15)*
- [x] Dashboard accuracy ✅ *(2026-05-15 19:45 UTC — resolved by P1-02)*
- [x] Dashboard + Insights require `require_view_reports` permission ✅ *(2026-05-15 19:46 UTC — V2-P2-01)*
  - Fixed: All 15+ dashboard/insights endpoints gated by `require_view_reports`
  - Files: `backend/app/api/endpoints/dashboard.py`, `backend/app/api/endpoints/insights.py`

### AI Insights

- [x] AI insights queries filter by COMPLETED status ✅ *(2026-05-15 19:47 UTC — P2-05)*
  - Fixed: `detect_dead_stock`, `suggest_reorder_quantity`, `analyze_sales_pattern` all filtered
  - File: `backend/app/services/ai_insights.py`

### Notifications

- [x] Background notification checks *(pre-2026-05-15)*
- [x] Notification UI page *(pre-2026-05-15)*
- [x] N8N webhook integration *(pre-2026-05-15)*
- [x] Notification deduplication uses timezone-aware datetime ✅ *(2026-05-15 19:48 UTC — P2-06)*
  - Fixed: All `datetime.now()` replaced with `datetime.now(timezone.utc)`
  - File: `backend/app/services/notification_service.py`

---

## Phase 4: Infrastructure & Code Quality

### Connection Pool

- [x] Database connection pool limits configured ✅ *(2026-05-15 19:47 UTC — P2-02)*
  - Fixed: `pool_size=10`, `max_overflow=20`, `pool_recycle=1800`
  - File: `backend/app/db/base.py`

### Scheduler

- [x] Scheduler preserves full tracebacks ✅ *(2026-05-15 19:49 UTC — P3-05)*
  - Fixed: All 9 task handlers use `logger.exception()` instead of `logger.error(str(e))`
  - File: `backend/app/services/scheduler.py`

### Security Module

- [x] JWT token creation uses timezone-aware datetime ✅ *(2026-05-15 19:48 UTC — P4-03)*
  - Fixed: `datetime.utcnow()` → `datetime.now(timezone.utc)`
  - File: `backend/app/core/security.py`

### Documentation Tracking

- [x] MEMORY.md and CLAUDE.md tracked in git ✅ *(2026-05-15 19:49 UTC — V2-P2-03)*
  - Fixed: `.gitignore` now includes `!MEMORY.md` and `!CLAUDE.md`
  - File: `.gitignore`

### PWA

- [x] Non-functional API cache rule removed ✅ *(2026-05-15 19:49 UTC — P2-03)*
  - Fixed: Removed `runtimeCaching` regex that matched `https://api.*` (app uses `/api`)
  - File: `frontend/vite.config.ts`

### Dead Code

- [x] Unused `require_admin()` and `require_admin_or_manager()` removed from `users.py` ✅ *(2026-05-15 19:44 UTC — P3-02)*

---

## Phase 5: Security Hardening

- [x] **P1-05:** SECRET_KEY strength enforced at startup ✅ *(2026-05-15 19:46 UTC)*
- [x] **P1-07:** Login rate limiting implemented ✅ *(2026-05-15 19:46 UTC)*
- [x] **P3-01:** Username enumeration via timing attack mitigated ✅ *(2026-05-15 19:46 UTC)*
- [x] JWT-based authentication (Bearer tokens, no cookies) *(pre-2026-05-15)*
- [x] Password hashing with bcrypt *(pre-2026-05-15)*
- [x] Role and permission-based access control *(pre-2026-05-15)*
- [x] CORS configured with explicit origins *(pre-2026-05-15)*
- [x] No public registration endpoint *(pre-2026-05-15)*
- [ ] Database password changed from default
- [x] Sync ingestion requires device registration + optional bearer token *(pre-2026-05-15)*

---

## Remaining Items Before Go-Live

### Must Complete (Operational)
1. [ ] SECRET_KEY rotated and set on all 5 deployment machines
2. [ ] Database password changed from default on all deployments
3. [ ] Demo credentials removed from release-facing login
4. [ ] Nightly backups automated on every client machine
5. [ ] Restore procedure tested on a real backup file
6. [ ] End-of-day closeout verified in pilot operations

### Should Complete (Quality)
7. [ ] Receipt printing verified with target printers
8. [ ] Barcode scanner input path verified
9. [ ] POS workflow tested on pharmacy workstation screens
10. [ ] Install steps documented and repeatable
11. [ ] Clean install verified on a fresh machine

---

## Sign-Off

| Role | Name | Date | Approved |
| ---- | ---- | ---- | -------- |
| Technical Lead | | | ☐ |
| Pharmacy Operations | | | ☐ |
| System Admin | | | ☐ |
