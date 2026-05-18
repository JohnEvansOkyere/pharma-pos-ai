# Go-Live Checklist — 5-Shop Pharmacy Rollout

> **Last updated:** 2026-05-18 21:37 UTC
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
10. [x] Install steps documented and repeatable ✅ *(2026-05-16 UTC — Docker Compose path fully documented in WINDOWS_LOCAL_DEPLOYMENT_RUNBOOK.md)*
11. [ ] Clean install verified on a fresh machine

---

## Phase 6: Cloud Vendor Admin Dashboard

> **Goal:** the vendor dashboard becomes a real command center for the whole pharmacy fleet: provisioning, support, risk detection, and trustworthy portfolio-level visibility from `pharma-pos-ai.vercel.app` without direct database access.
>
> **Architecture constraint:** each pharmacy remains local-first. The cloud only knows what a client machine has uploaded through the sync outbox, then what has been projected into cloud read models. Therefore:
> - `last_seen_at` proves a device contacted the cloud; it does **not** by itself prove the local till is healthy.
> - missing sales data may mean “no sales”, “offline”, or “not yet uploaded” unless explicit heartbeat telemetry exists.
> - every business chart should expose **data freshness** and **reconciliation state** beside the metric, so stale data is never mistaken for live truth.

### 6.1 Implemented Baseline — Provisioning & Basic Fleet View

- [x] `GET /admin/organizations` — list all orgs with branch + device counts ✅ *(2026-05-18 21:26 UTC)*
- [x] `POST /admin/organizations` — create org ✅ *(2026-05-18 21:26 UTC)*
- [x] `PATCH /admin/organizations/{org_id}` — update org metadata / active status ✅ *(2026-05-18 21:26 UTC)*
- [x] `GET /admin/organizations/{org_id}/branches` — list branches ✅ *(2026-05-18 21:26 UTC)*
- [x] `POST /admin/organizations/{org_id}/branches` — create branch ✅ *(2026-05-18 21:26 UTC)*
- [x] `GET /admin/devices` — list devices across orgs with status and `last_seen_at` ✅ *(2026-05-18 21:26 UTC)*
- [x] `GET /admin/command-center` — admin-only fleet summary for reachability, data freshness, money pulse, stock risk, and attention queue ✅ *(2026-05-18 21:37 UTC)*
- [x] `POST /admin/organizations/{org_id}/branches/{branch_id}/devices` — provision device and return the raw token once ✅ *(2026-05-18 21:26 UTC)*
- [x] `PATCH /admin/devices/{device_id}/status` — enable / disable device ✅ *(2026-05-18 21:26 UTC)*
- [x] `POST /admin/devices/{device_id}/rotate-token` — rotate per-device sync token ✅ *(2026-05-18 21:26 UTC)*
- [x] Admin tenancy endpoints require `require_vendor_admin` ✅ *(2026-05-18 21:26 UTC)*
- [x] `/clients` page shows pharmacies, total devices, active devices, synced today ✅ *(2026-05-18 21:26 UTC)*
- [x] `/clients` page shows expandable org → device tree, device status, last sync age, enable/disable, token rotation ✅ *(2026-05-18 21:26 UTC)*
- [x] `"Provision New Client"` wizard creates org → branch → device and shows the env block once ✅ *(2026-05-18 21:26 UTC)*
- [x] Sidebar includes vendor-only `"Clients"` navigation item ✅ *(2026-05-18 21:26 UTC)*
- [x] `/clients` now includes admin-only command center cards for fleet coverage, needs-attention count, today revenue, stock value at risk, sync/data freshness, attention queue, and pharmacy pulse table ✅ *(2026-05-18 21:37 UTC)*

### 6.2 Command-Center Contract — Questions the Home Screen Must Answer

- [/] **Can every pharmacy operate right now?** Cloud reachability is shown for orgs, devices, stale devices, never-synced devices, and branches without healthy devices; true local health still needs heartbeat telemetry. *(updated 2026-05-18 21:37 UTC)*
- [/] **Can I trust the cloud data I am looking at?** Upload freshness, projection lag, failed projections, unprojected events, duplicates, and data-trust status are shown; full reconciliation severity beside every metric is still pending. *(updated 2026-05-18 21:37 UTC)*
- [/] **Where is money at risk today?** Today/yesterday/trailing-7-day revenue and per-client revenue are shown; sales drop-offs, no-sales-during-hours alerts, void/refund spikes, and concentration analytics remain pending. *(updated 2026-05-18 21:37 UTC)*
- [/] **Where is stock at risk today?** Fleet stock risk totals now show out-of-stock, low-stock, expiry counts, quantity on hand, and value at risk; ranked branch/product drilldowns remain pending. *(updated 2026-05-18 21:37 UTC)*
- [x] **What needs my intervention first?** Command center attention queue ranks projection failures, expired stock, branch coverage, stale devices, and never-synced devices by severity. ✅ *(2026-05-18 21:37 UTC)*

### 6.3 P0 Owner Intelligence — Must-Have Before Scaling Beyond Early Clients

#### Fleet Health

- [x] Portfolio KPI strip: active pharmacies, active branches, active devices, stale devices, never-synced devices, disabled devices, branches with zero devices. ✅ *(2026-05-18 21:37 UTC)*
- [/] Fleet health table grouped by organization → branch → device with:
  - latest contact time
  - age bucket (`<1h`, `1–24h`, `>24h`, never)
  - current device status
  - first provisioned date
  - branch/device counts
  - immediate alert badge when a branch has no healthy device. *(updated 2026-05-18 21:37 UTC — org/device tree and pharmacy pulse exist; branch-level table is still pending)*
- [x] “Needs attention now” queue listing the oldest stale devices, never-synced devices, and branches with no online device. ✅ *(2026-05-18 21:37 UTC)*
- [ ] Drill-down from each pharmacy to branches and devices without leaving the command-center context. *(2026-05-18 21:26 UTC)*

#### Sync Pipeline & Data Freshness

- [/] Per organization and branch:
  - last event received
  - last event projected
  - projection lag
  - ingested event count
  - projected event count
  - failed projection count
  - duplicate delivery count
  - unprojected event backlog. *(updated 2026-05-18 21:37 UTC — fleet-level and per-org projection failures exist; branch-level sync pipeline still pending)*
- [ ] Per device:
  - last sync seen
  - event count over the last 24h / 7d
  - latest accepted local sequence number
  - gap detection for missing sequence ranges
  - warning when a device is contacting the cloud but producing no business events unexpectedly. *(2026-05-18 21:26 UTC)*
- [x] Explicit freshness banner on every portfolio metric: `fresh`, `delayed`, `stale`, `unsafe`, or `unknown`. ✅ *(2026-05-18 21:37 UTC)*
- [ ] Manual admin controls:
  - run projection
  - retry failed projection
  - inspect latest failed event
  - open the related reconciliation issue. *(2026-05-18 21:26 UTC)*

#### Data Trust & Reconciliation

- [ ] Fleet-wide reconciliation summary:
  - critical / high / medium issue counts
  - affected pharmacies / branches
  - oldest unresolved issue
  - acknowledged vs unresolved issues. *(2026-05-18 21:26 UTC)*
- [ ] Reconciliation issue drill-down with the current known issue classes:
  - projection failures present
  - negative product stock
  - negative batch quantity
  - orphan batch snapshot
  - product-vs-batch quantity mismatch
  - latest movement `stock_after` mismatch. *(2026-05-18 21:26 UTC)*
- [/] Every business summary card should display whether its scope is reconciled, partially reconciled, or currently unsafe to trust. *(updated 2026-05-18 21:37 UTC — data-trust status is visible globally; scope-specific reconciliation remains pending)*

#### Money Pulse

- [/] Today / yesterday / trailing 7-day revenue by organization and branch. *(updated 2026-05-18 21:37 UTC — fleet and per-organization revenue exist; branch-level view remains pending)*
- [ ] Sales count, item count, average basket size, and revenue trend by branch. *(2026-05-18 21:26 UTC)*
- [ ] “No reported sales today” alert for branches expected to be operating, qualified by freshness so offline branches are not mistaken for zero-sales branches. *(2026-05-18 21:26 UTC)*
- [ ] Portfolio ranking:
  - top branches by revenue
  - bottom branches by revenue
  - biggest day-over-day gain
  - biggest day-over-day drop. *(2026-05-18 21:26 UTC)*
- [ ] Refund / void anomaly panel once those events are projected into the cloud reporting model. *(2026-05-18 21:26 UTC)*

#### Stock Risk

- [x] Fleet-wide stock risk summary:
  - out-of-stock product count
  - low-stock product count
  - near-expiry batch count
  - expired batch count
  - quantity on hand
  - value at risk. ✅ *(2026-05-18 21:37 UTC)*
- [ ] Rank organizations / branches by:
  - most out-of-stock products
  - most low-stock products
  - highest expiry value at risk
  - highest expired stock value. *(2026-05-18 21:26 UTC)*
- [ ] Top urgent stock list with product, SKU, branch, quantity, threshold, days to expiry, and estimated value at risk. *(2026-05-18 21:26 UTC)*
- [ ] Product-level drill-down across branches so you can see whether a stockout is local to one branch or systemic across a client. *(2026-05-18 21:26 UTC)*

### 6.4 P1 Operational Intelligence — Needed For Support, Accountability, and Calm

#### Local Installation Telemetry — Requires New Heartbeat / Diagnostic Sync Events

- [ ] Client heartbeat telemetry event carrying:
  - app version
  - database connectivity status
  - local scheduler status
  - local outbox pending count
  - oldest unsent outbox event age
  - last successful backup time
  - last restore drill time / status
  - free disk space
  - server clock skew
  - uptime / last restart. *(2026-05-18 21:26 UTC)*
- [ ] Installation readiness score per device / branch using heartbeat data, not just “last seen”. *(2026-05-18 21:26 UTC)*
- [ ] Alert when a machine is online but:
  - backups are stale
  - restore drills are overdue
  - outbox backlog is growing
  - disk space is low
  - scheduler is stopped
  - software version is behind the supported release. *(2026-05-18 21:26 UTC)*

#### Client Lifecycle & Support

- [ ] Client profile page with organization contacts, branches, devices, install date, last activity, and internal notes. *(2026-05-18 21:26 UTC)*
- [ ] Provisioning lifecycle state:
  - created
  - token issued
  - first sync received
  - first sale received
  - operating normally
  - stale / suspended. *(2026-05-18 21:26 UTC)*
- [ ] Support timeline per client:
  - provisioning events
  - token rotations
  - device disables / re-enables
  - first / last sync
  - reconciliation incidents
  - operator acknowledgements. *(2026-05-18 21:26 UTC)*
- [ ] Search and filters by organization, branch, device UID, health state, stale age, and risk type. *(2026-05-18 21:26 UTC)*

#### Security & Control

- [ ] Surface disabled / retired devices separately from active devices. *(2026-05-18 21:26 UTC)*
- [ ] Show recent token rotation history and age of current token policy where available. *(2026-05-18 21:26 UTC)*
- [ ] Audit vendor actions from the dashboard:
  - organization create/update
  - branch create/update
  - device provision
  - status toggle
  - token rotation. *(2026-05-18 21:26 UTC)*
- [ ] Alert on repeated rejected sync attempts for invalid token, wrong tenant, or disabled device once those security events are aggregated for vendor review. *(2026-05-18 21:26 UTC)*

### 6.5 P2 Portfolio Intelligence — Useful Once The Fleet Is Alive

- [ ] Portfolio trend dashboard:
  - client count growth
  - active branch growth
  - synced-device coverage over time
  - gross merchandise volume trend
  - revenue concentration by top clients. *(2026-05-18 21:26 UTC)*
- [ ] Cross-client benchmarking:
  - revenue per branch
  - items per sale
  - sales per day
  - stockout rate
  - expiry loss risk
  - low-stock burden. *(2026-05-18 21:26 UTC)*
- [ ] Commercial watchlist:
  - clients with falling sales
  - clients with repeated stock risk
  - clients not fully onboarded
  - clients likely needing follow-up or training. *(2026-05-18 21:26 UTC)*
- [ ] Weekly executive digest generated from trusted cloud data only, with freshness and reconciliation warnings embedded. *(2026-05-18 21:26 UTC)*

### 6.6 Current Architecture Coverage vs Required New Work

- [x] **Already available from current cloud read models:** branch sales, inventory movement summaries, sync-health aggregates, stock-risk summaries, low-stock lists, expiry-risk lists, and reconciliation issues ✅ *(2026-05-18 21:26 UTC)*
- [x] **Already available from current tenancy models:** organizations, branches, devices, device status, and `last_seen_at` ✅ *(2026-05-18 21:26 UTC)*
- [x] **New admin command-center aggregate:** `/admin/command-center` combines tenancy, ingested sync events, projected sales facts, product snapshots, and batch snapshots into one admin-only fleet summary ✅ *(2026-05-18 21:37 UTC)*
- [ ] **Requires richer queries over existing ingested events:** per-device event counts, per-device projection counts, stale ranking, sequence-gap detection, unprojected backlog, and fleet-level alert rollups. *(2026-05-18 21:26 UTC)*
- [ ] **Requires new synced telemetry events from local installs:** backup age, restore-drill age, local outbox backlog, app version, scheduler status, disk space, uptime, and clock skew. *(2026-05-18 21:26 UTC)*
- [ ] **Requires additional projected business facts before it can be trusted in the cloud:** refunds, voids, richer payment mix, and any revenue/anomaly metric that depends on those event types. *(2026-05-18 21:26 UTC)*

---

## Sign-Off

| Role | Name | Date | Approved |
| ---- | ---- | ---- | -------- |
| Technical Lead | | | ☐ |
| Pharmacy Operations | | | ☐ |
| System Admin | | | ☐ |
