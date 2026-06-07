# Go-Live Checklist — 5-Shop Pharmacy Rollout

> **Last updated:** 2026-05-19 UTC
> **Source audits:** `docs/audits/2026-05-15-production-readiness-audit.md`, `docs/audits/2026-05-15-production-readiness-audit-v2.md`, `docs/ai/AI_CLOUD_DASHBOARD_ASSESSMENT_2026-05-18.md`, `docs/ai/2026-05-19-cloud-ai-dashboard-audit.md`
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

- [x] **P1-03:** Prescription, customer-ID, and controlled-drug checkout gates superseded by current client workflow ✅ *(updated 2026-05-19 09:50 UTC)*
  - Product decision: `prescription_status`, `requires_id`, and `is_narcotic` remain catalog metadata only for the current Ghana deployment.
  - Current POS behavior: sale creation does not block checkout solely because those flags are set.
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
- [x] Backend tests pass — 122/122 passing ✅ *(2026-05-19 09:50 UTC)*
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

- [/] **Can every pharmacy operate right now?** Cloud reachability is shown for orgs, devices, stale devices, never-synced devices, and branches without healthy devices; local heartbeat telemetry now reports database, scheduler, outbox, backup, restore-drill, disk, uptime, and readiness state. Remaining gap: branch operating-hours rules and field verification on deployed machines. *(updated 2026-05-19 09:50 UTC)*
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

- [/] Client heartbeat telemetry event carrying:
  - app version
  - database connectivity status
  - local scheduler status
  - local outbox pending count
  - oldest unsent outbox event age
  - last successful backup time
  - last restore drill time / status
  - free disk space
  - server clock skew
  - uptime / last restart. *(updated 2026-05-19 09:50 UTC — all listed telemetry is synced except true clock-skew calculation; server clock timestamp is included for future drift comparison)*
- [/] Installation readiness score per device / branch using heartbeat data, not just “last seen”. *(updated 2026-05-19 09:50 UTC — device heartbeat readiness is projected; command center shows fleet/org readiness counts and attention items, but a dedicated branch drilldown remains pending)*
- [/] Alert when a machine is online but:
  - backups are stale
  - restore drills are overdue
  - outbox backlog is growing
  - disk space is low
  - scheduler is stopped
  - software version is behind the supported release. *(updated 2026-05-19 09:50 UTC — heartbeat warnings cover stale backups, overdue restore drills, failed/old outbox data, and scheduler/database failures; low-disk thresholds and supported-version policy remain pending)*

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
- [/] **Requires new synced telemetry events from local installs:** backup age, restore-drill age, local outbox backlog, app version, scheduler status, disk space, uptime, and clock skew. *(updated 2026-05-19 09:50 UTC — heartbeat event and projection are implemented; true clock-skew comparison remains pending)*
- [/] **Requires additional projected business facts before it can be trusted in the cloud:** refunds, voids, richer payment mix, and any revenue/anomaly metric that depends on those event types. *(updated 2026-05-19 09:50 UTC — `SALE_REVERSED` already syncs and restores cloud stock movement/snapshots; dedicated financial reversal/void anomaly facts and richer payment analytics remain pending)*

---

## Phase 7: Cloud AI Dashboard Audit Follow-Up

> **Goal:** make cloud dashboard and AI advice trustworthy before expanding into CEO-grade recommendations. The two final AI audit reports agree that the sync/projection foundation is useful, but cloud facts needed P0 correctness fixes before the AI layer could safely calculate velocity, days-of-stock, trends, or proactive findings.

### 7.1 P0 Data Correctness — Required Before Strong AI Advice

- [x] Consolidate the two final cloud AI dashboard assessments into this go-live checklist. ✅ *(2026-05-19 01:44 UTC)*
  - Sources: `docs/ai/AI_CLOUD_DASHBOARD_ASSESSMENT_2026-05-18.md`, `docs/ai/2026-05-19-cloud-ai-dashboard-audit.md`

- [x] Preserve original sale business time in cloud reporting facts. ✅ *(2026-05-19 01:44 UTC)*
  - Fixed: `SALE_CREATED` sync payload now includes `occurred_at` from the local sale timestamp.
  - Fixed: `CloudSaleFact.occurred_at` added with migration.
  - Fixed: cloud sales reports, vendor command center revenue windows, AI chat sales summaries, and AI weekly report sales windows use `coalesce(occurred_at, created_at)`.
  - Files: `backend/app/api/endpoints/sales.py`, `backend/app/models/cloud_projection.py`, `backend/app/api/endpoints/cloud_reports.py`, `backend/app/api/endpoints/admin_tenancy.py`, `backend/app/services/ai_manager_service.py`, `backend/app/services/ai_weekly_report_service.py`, `backend/alembic/versions/j0e1f2a3b4c5_add_occurred_at_to_cloud_sale_facts.py`

- [x] Project normal sales into cloud inventory movement facts. ✅ *(2026-05-19 01:44 UTC)*
  - Fixed: each `SALE_CREATED` item now creates a negative `CloudInventoryMovementFact` row.
  - Fixed: sale movement facts carry `occurred_at` so delayed sync does not distort movement windows when the timestamp is available.
  - Files: `backend/app/models/cloud_projection.py`, `backend/app/services/cloud_projection_service.py`, `backend/alembic/versions/j0e1f2a3b4c5_add_occurred_at_to_cloud_sale_facts.py`

- [x] Preserve local batch identity in sale sync payloads and projection. ✅ *(2026-05-19 01:44 UTC)*
  - Fixed: sale payload item lines include `batch_id` captured at FEFO allocation time.
  - Fixed: cloud projection prefers `batch_id` and falls back to `batch_number` only for older payloads.
  - Fixed: split-batch FEFO sales preserve the correct batch ID per sale line.
  - Files: `backend/app/api/endpoints/sales.py`, `backend/app/services/cloud_projection_service.py`

- [x] Add a one-time full snapshot sync for existing installs. ✅ *(2026-05-19 01:52 UTC)*
  - Fixed: `POST /system/enqueue-cloud-snapshot` enqueues active product and batch snapshot events into the local outbox for first-time cloud hydration.
  - Fixed: snapshot generation recalculates sellable stock, preserves quarantined batch state, adds snapshot metadata, and writes an audit log.
  - Files: `backend/app/api/endpoints/system_ops.py`, `backend/app/schemas/system.py`, `backend/app/services/full_snapshot_sync_service.py`, `backend/tests/test_full_snapshot_sync_service.py`

- [x] Add AI trust gates before strong business advice. ✅ *(2026-05-19 02:10 UTC — chat; 2026-05-19 UTC — weekly reports)*
  - Done: AI manager chat prepends a DATA TRUST WARNING when projection failures, stale/no sync, or critical/high reconciliation issues exist.
  - Done: Weekly report executive summary prepends a DATA TRUST WARNING when projection failures, staleness > 48h, or critical/high reconciliation issues exist.
  - Pending: cloud dashboard briefing/cards still need per-metric freshness badges embedded in the card UI.

### 7.2 P1 Intelligence Foundation

- [x] Add cloud product velocity calculation from projected sale movement facts. ✅ *(2026-05-19 02:02 UTC)*
  - Fixed: `GET /cloud-reports/stock-velocity` calculates units sold, movement count, average daily units sold, confidence, and urgency status from `SALE_CREATED` movement facts only.
  - Fixed: AI manager tool results now include `stock_velocity`, and the cloud dashboard shows a Stock Velocity priority list.
  - Files: `backend/app/api/endpoints/cloud_reports.py`, `backend/app/schemas/cloud_reports.py`, `backend/app/services/cloud_stock_velocity_service.py`, `backend/app/services/ai_manager_service.py`, `frontend/src/services/api.ts`, `frontend/src/pages/CloudDashboardPage.tsx`
- [x] Add days-of-stock remaining using current stock divided by sales velocity. ✅ *(2026-05-19 02:02 UTC)*
  - Fixed: velocity rows return `days_of_stock_remaining`, `estimated_stockout_date`, `units_needed`, and urgency statuses including `out_of_stock`, `critical`, `urgent`, `reorder_soon`, `stable`, and `no_velocity`.
  - Files: `backend/app/services/cloud_stock_velocity_service.py`, `backend/tests/test_cloud_reports.py`, `backend/tests/test_ai_manager.py`, `frontend/src/pages/CloudDashboardPage.test.tsx`
- [x] Add deterministic week-over-week revenue comparison. ✅ *(2026-05-19 02:10 UTC)*
  - Fixed: `GET /cloud-reports/revenue-comparison` compares the current period with the immediately previous equal period using cloud sale business time.
  - Fixed: AI manager tool results now include `revenue_comparison`, and the cloud dashboard shows a Branch Trend anomaly list.
  - Files: `backend/app/api/endpoints/cloud_reports.py`, `backend/app/schemas/cloud_reports.py`, `backend/app/services/cloud_sales_trend_service.py`, `backend/app/services/ai_manager_service.py`, `frontend/src/services/api.ts`, `frontend/src/pages/CloudDashboardPage.tsx`
- [x] Add cloud dead-stock and slow-mover detection. ✅ *(2026-05-19 UTC)*
  - Fixed: `GET /cloud-reports/dead-stock` returns products with positive stock and zero or very low sales velocity from projected movement facts.
  - Fixed: products with zero sales are flagged as `dead_stock`; products below 0.3 units/day average are `slow_mover`.
  - Fixed: AI manager recognises dead-stock/slow-mover questions and includes a summary with the top dead-stock item.
  - Fixed: Cloud dashboard shows a "Dead Stock &amp; Slow Movers" RiskTable alongside Stock Velocity.
  - Files: `backend/app/services/cloud_dead_stock_service.py`, `backend/app/schemas/cloud_reports.py`, `backend/app/api/endpoints/cloud_reports.py`, `backend/app/services/ai_manager_service.py`, `frontend/src/services/api.ts`, `frontend/src/pages/CloudDashboardPage.tsx`, `backend/tests/test_cloud_reports.py`
- [/] Add branch anomaly detection for sales drops and no-sales-during-hours alerts. *(updated 2026-05-19 02:10 UTC)*
  - Done: branch revenue comparison flags `no_sales_current`, `severe_drop`, `drop`, `growth`, `new_sales`, and `stable`.
  - Pending: operating-hours-aware no-sales alerts still need branch opening-hours configuration or heartbeat/business-hours rules.

### 7.3 P2 Persistent CEO Workbench

- [x] Add persistent `ai_findings` records with severity, evidence, freshness, reconciliation state, confidence, status, and due date. ✅ *(2026-05-19 03:00 UTC)*
  - Done: `AIFinding` model added to `ai_report.py` with fields: type, severity, title, summary, affected_count, action_hint, fingerprint, evidence (JSON), data_trust_status, confidence, status, due_date, snoozed_until, resolved_at, last_seen_at.
  - Done: Alembic migration `k1f2a3b4c5d6_add_ai_findings.py` creates the `ai_findings` table.
  - Done: `AIFindingService` with `upsert_findings()`, `get_findings()`, `update_status()`. Upsert refreshes open/snoozed findings without clobbering dismissed/resolved decisions. Fingerprint = `"<branch_id|0>:<type>"` ensures one row per scope per finding type.
  - Done: `GET /ai-manager/briefing?persist=true` upserts all findings (up to 50) and then returns the top N capped view.
  - Done: `GET /ai-manager/findings` lists active (open/acknowledged/snoozed) findings; supports `status=` filter.
  - Done: `PATCH /ai-manager/findings/{finding_id}` updates status with auto-expire of snoozed findings on read.
  - Files: `backend/app/models/ai_report.py`, `backend/app/models/__init__.py`, `backend/alembic/versions/k1f2a3b4c5d6_add_ai_findings.py`, `backend/app/services/ai_finding_service.py`, `backend/app/schemas/ai_manager.py`, `backend/app/api/endpoints/ai_manager.py`
- [x] Add `ai_recommendations` / decision workflow for accept, snooze, dismiss, and resolve. ✅ *(2026-05-19 03:00 UTC)*
  - Done: `PATCH /ai-manager/findings/{finding_id}` supports status transitions: open → acknowledged, snoozed, dismissed, resolved. Snoozed findings auto-reopen when `snoozed_until` is past. Resolved findings record `resolved_at` and `resolved_by_user_id`.
  - Done: Cloud dashboard Owner Briefing panel has "Save Findings" button (calls persist=true briefing). Saved Findings panel below shows active findings with Acknowledge / Snooze 7d / Resolve / Dismiss action buttons.
  - Done: 3 new finding tests (persist saves, status update, no-duplicate upsert). 119 backend tests pass.
  - Files: `backend/app/api/endpoints/ai_manager.py`, `frontend/src/pages/CloudDashboardPage.tsx`, `frontend/src/services/api.ts`, `backend/tests/test_ai_manager.py`
- [x] Add `GET /ai-manager/briefing` for the top ranked actions. ✅ *(2026-05-19 UTC)*
  - Done: On-demand endpoint generates ranked findings from all existing deterministic services (stock velocity, dead stock, expiry risk, revenue comparison, sync health, reconciliation). No DB persistence — always fresh.
  - Finding types: `stock_out`, `critical_velocity`, `urgent_velocity`, `expired_batch`, `near_expiry`, `dead_stock`, `slow_mover`, `revenue_drop`, `revenue_decline`, `sync_failure`, `stale_sync`, `no_sync`, `reconciliation`.
  - Each finding: type, severity, title, summary, affected_count, action_hint.
  - Response includes `data_trust_status` (ok/degraded/unsafe) and `data_trust_notes`.
  - Files: `backend/app/services/ai_briefing_service.py` (new), `backend/app/schemas/ai_manager.py`, `backend/app/api/endpoints/ai_manager.py`, `backend/tests/test_ai_manager.py`
- [x] Show the briefing at the top of the cloud dashboard. ✅ *(2026-05-19 UTC)*
  - Done: Owner Briefing panel renders at top of cloud dashboard when there are findings. Color-coded by severity (critical = red, high = amber, medium = gray). Shows data trust status badge, notes, and action hints.
  - Files: `frontend/src/pages/CloudDashboardPage.tsx`, `frontend/src/services/api.ts`

### 7.4 P3 Conversation Quality

- [x] Persist AI chat sessions and messages. ✅ *(2026-05-19 13:00 UTC)*
  - Done: `AIChatSession` and `AIChatMessage` persist cloud dashboard AI conversations per user/org/branch scope.
- [x] Pass recent conversation history to the LLM for follow-up continuity. ✅ *(2026-05-19 13:00 UTC)*
  - Done: chat requests load the latest session messages and pass conversation history into OpenAI/Groq/Claude adapters.
- [ ] Replace raw dict prompts with structured evidence packs and output schema. *(2026-05-19 01:44 UTC)*
- [x] Add branch and product names beside branch/product metrics returned to the AI and dashboard. ✅ *(2026-05-19 UTC)*
  - Done: AI manager `_branch_sales` returns `branch_name`. Stock velocity service returns `branch_name`. Weekly report `_branch_sales` returns `branch_name`. AI manager branch keyword response uses branch name.
  - Done: Dead stock and velocity dashboard RiskTables show branch name from API.
  - Pending: branch names in raw LLM evidence pack (raw dict prompt still uses IDs in some tool_results). Product names are already present in velocity/dead_stock/stock_risk items.

---

## Phase 8: Cloud Reporting Portal / CEO Source of Truth

> **Goal:** keep the deployed cloud app from looking like a second pharmacy POS with a separate product/sales database. The cloud deployment should be a reporting and owner-intelligence portal fed by local sync projections. The local installation remains the operational source for dispensing, products, stock receipt, sales, voids, refunds, and day-to-day till work.

### 8.1 P0 Confusion Guardrails

- [x] Add explicit app mode: `local_pos` for pharmacy installations and `cloud_reporting` for the deployed reporting portal. ✅ *(2026-05-19 11:33 UTC)*
  - Fixed: backend `APP_MODE` and frontend `VITE_APP_MODE` are now explicit deployment choices.
- [x] In `cloud_reporting` mode, hide local operational pages from the frontend: POS, Products, Sales, Stock Adjustments, Suppliers, Notifications, local Dashboard, and local Settings unless a specific cloud-safe setting is required. ✅ *(2026-05-19 11:33 UTC)*
  - Fixed: cloud reporting mode sidebar shows only cloud reporting/admin routes and operational routes redirect away.
- [x] In `cloud_reporting` mode, backend must reject unsafe local operational write endpoints so users cannot create cloud-only sales/products by accident. ✅ *(2026-05-19 11:33 UTC)*
  - Fixed: unsafe writes to local operational endpoints return `403` in cloud reporting mode.
- [x] Make cloud-reporting default landing route go to `/cloud-dashboard` for pharmacy admins/managers and `/clients` for vendor admin users. ✅ *(2026-05-19 11:33 UTC)*
- [x] Document required deployment env values for local POS and cloud reporting deployments. ✅ *(2026-05-19 11:33 UTC)*
  - Fixed: Render runbook and env examples document `APP_MODE`; Vercel runbook documents `VITE_APP_MODE`.

### 8.2 P0 Dashboard Metric Semantics

- [x] Reconcile local dashboard vs cloud dashboard item-count semantics. The cloud "items sold" KPI must clearly match local behavior: either units sold or sale-line count, not a hidden mixture. ✅ *(2026-05-19 14:56 UTC)*
  - Fixed: cloud sale projection now stores `CloudSaleFact.item_count` as total units sold (`sum(item.quantity)`), matching local dashboard `total_items_sold`.
  - Fixed: admin reconciliation repair type `repair_sale_item_counts` recalculates existing already-projected cloud sale facts from the accepted `SALE_CREATED` payload so old line-count values can be corrected without changing local POS data. ✅ *(2026-05-19 17:11 UTC)*
- [x] Add tests proving cloud sales summary totals use completed sale facts, original business time, and the selected item-count definition. ✅ *(2026-05-19 14:56 UTC)*
  - Done: projection tests now prove split sale lines store unit totals; cloud report tests verify average transaction value and business-time sales summary behavior.
- [x] Add a visible data freshness/trust state to CEO KPI blocks so stale sync is not mistaken for live business performance. ✅ *(2026-05-19 14:56 UTC)*
  - Done: the cloud dashboard has a dedicated **Data Health** section with one trust state (`Fresh`, `Delayed`, `Stale`, `Unsafe`, or `Unknown`) plus sync freshness, projection, reconciliation, and inventory activity details.
  - Updated: business KPI cards no longer show technical sync/reconciliation cards beside revenue/profit. *(2026-05-19 15:40 UTC)*

### 8.3 P1 CEO KPI Coverage

> **Decision audit (2026-05-19):** Five KPIs were identified as genuinely affecting owner decisions that are not yet on the dashboard. Each was validated against available cloud projection data before being added here.

- [x] **Gross Profit KPI card** — `sum(sale_revenue) - sum(cost_price × units_sold from movement facts)`. Without margin, revenue is vanity; a high-revenue branch with 5% margin is worse than a lower-revenue branch at 40%. ✅ *(2026-05-19)*
  - `GET /cloud-reports/profit-summary` → `CloudProfitSummary` (revenue, cost, gross_profit, margin_%, products with/without cost data)
  - New KPI card on cloud dashboard.
- [x] **Total Stock Value card** — `sum(cost_price × total_stock)` across active product snapshots. Shows how much capital is locked in inventory across the fleet. ✅ *(2026-05-19)*
  - `GET /cloud-reports/stock-value` → `CloudStockValueSummary` (cost value, retail value, products_valued)
  - New KPI card on cloud dashboard.
- [x] **Dead Stock Value (GHS)** — added `value_at_risk = cost_price × total_stock` to Dead Stock & Slow Movers table. ✅ *(2026-05-19)*
  - `CloudDeadStockService` now includes `value_at_risk` per item; shown inline in the table secondary line.
- [x] **Average Transaction Value card** — `total_revenue ÷ sales_count` added to `CloudSalesSummary` response and new KPI card. ✅ *(2026-05-19)*
- [x] **Stockout Revenue Estimate** — `average_daily_units_sold × selling_price` per out-of-stock product with velocity. ✅ *(2026-05-19)*
  - `GET /cloud-reports/stockout-impact` → `CloudStockoutImpact` (total daily loss, per-product breakdown)
  - New KPI card (daily loss total) and new Stockout Revenue Loss RiskTable on cloud dashboard.
- [ ] Add branch ranking and comparison sections: top/bottom branch by revenue, day-over-day change, biggest drop, no-reported-sales state qualified by freshness. *(2026-05-19 11:29 UTC)*
- [ ] Add cloud-safe drilldowns for stock value, slow movers, expiry risk, and dead stock without exposing local POS write workflows. *(2026-05-19 11:29 UTC)*

### 8.4 P1 AI Reporting and Charts

- [ ] Keep AI on the cloud dashboard/reporting side only; it must not mutate sales, stock, products, or users. *(2026-05-19 11:29 UTC)*
- [ ] Let AI generate chart/report definitions only from structured backend evidence packs, with chart data coming from trusted backend endpoints rather than invented LLM numbers. *(2026-05-19 11:29 UTC)*
- [ ] Add exportable CEO report output with embedded freshness/reconciliation warnings. *(2026-05-19 11:29 UTC)*

---

## Phase 9: CEO AI Intelligence — From Keyword Matching to Real Intelligence

> **Goal:** The AI is the primary value proposition of this product for the CEO. It must understand any question about the pharmacy in plain English, answer from real data only, never guess, and find the CEO proactively instead of waiting to be asked.
>
> **Architecture decision (2026-05-19):** Replace the current keyword-matching `_compose_answer` layer with **LLM Tool Use orchestration**. The LLM decides which data functions to call based on the question, calls all relevant ones, combines the results, and reasons freely over them. The pre-built service functions (sales, velocity, dead stock, trends, reconciliation, etc.) become **tools** the LLM selects — not routes triggered by hardcoded keywords. This is the same pattern used by Salesforce Einstein Copilot, Microsoft Copilot for Business Central, and Intercom Fin.
>
> **Why Tool Use over Text-to-SQL:** Business rules (FEFO, completed-sales-only revenue, `coalesce(occurred_at, created_at)` time windows, multi-tenant isolation) are already correctly encoded in the existing service functions. Text-to-SQL bypasses those rules. Tool Use keeps accuracy guarantees, is testable, schema-change-safe, and sandboxed. Text-to-SQL is only appropriate with a dedicated semantic layer — which is itself tool use at the schema level.

### 9.1 LLM Tool Use Architecture (Replace Keyword Matching)

- [x] Define the existing service functions as formal LLM tools with JSON schemas: `get_sales_summary`, `get_branch_sales`, `get_product_sales`, `get_stock_risk`, `get_stock_velocity`, `get_dead_stock`, `get_revenue_comparison`, `get_sync_health`, `get_reconciliation`, `get_inventory_summary`. ✅ *(2026-05-19)*
  - Done: `TOOL_SCHEMAS` (10 tools, OpenAI function-calling format) added to `ai_manager_service.py`.
- [x] Remove `_compose_answer` keyword-matching routing from the LLM-configured path. ✅ *(2026-05-19)*
  - Done: `answer()` now splits — LLM-configured path uses `generate_answer_with_tools` with `_ceo_system_prompt`; deterministic/no-key fallback still uses `_compose_answer` for test and offline safety.
- [x] Remove `_provider_prompt` and replace with CEO-appropriate `_ceo_system_prompt` that gives the LLM full reasoning freedom. ✅ *(2026-05-19)*
  - Done: `_provider_prompt` deleted. `_ceo_system_prompt` does not anchor the LLM to a keyword-matched baseline.
- [x] Implement OpenAI function-calling and Anthropic tool-use protocol in `ai_llm_provider.py`. ✅ *(2026-05-19)*
  - Done: `generate_answer_with_tools()`, `_openai_tool_loop()` (handles OpenAI + Groq), `_claude_tool_loop()`, `_to_anthropic_tools()` added. Agentic loop capped at `MAX_TOOL_ITERATIONS = 5`.
- [x] Tool dispatcher caches pre-fetched data for default period calls (zero extra DB round-trips); does a fresh query only when LLM asks for `today`/`yesterday`. ✅ *(2026-05-19)*
  - Done: `_make_tool_dispatcher()` serves `prefetched` dict on `period="period"` and queries live for `today`/`yesterday`.
- [x] All tool results come from the existing validated service functions — the LLM selects and combines approved tool outputs. ✅ *(2026-05-19)*
- [x] Add a final numeric answer verifier so unsupported LLM figures are rejected before the answer is returned. ✅ *(2026-05-19 23:59 UTC)*
  - Done: `AIManagerService._verify_answer_numbers()` scans final answers for numeric claims and falls back to the deterministic answer if a number is not present in approved tool evidence.
- [x] Return tool-call traceability with chat responses. ✅ *(2026-05-19 23:59 UTC)*
  - Done: `generate_answer_with_tools()` now returns `tool_trace` entries containing tool name, arguments, and result. `AIManagerChatResponse` exposes `tool_trace` and `verification`.
- [x] Write regression tests: the LLM tool-use path must pass all existing AI manager test cases. ✅ *(2026-05-19)*
  - Done: all 25 `test_ai_manager` tests pass. Coverage now includes external-answer numeric verification, returned tool trace, and Telegram CEO message routing.

### 9.2 Proactive Push Alerts (CEO Gets Found, Not the Other Way Around)

> **Key insight:** A CEO running 5 shops will not open the dashboard every morning. The AI must come to them. Pull-only Q&A is the secondary interface; push is primary.

- [x] Real-time anomaly detection scheduler job: runs every 45 minutes, detects critical/high findings via `AIBriefingService` (out-of-stock, expired batch, revenue drop, sync failure, stale sync). ✅ *(2026-05-19)*
  - Done: `TelegramAlertService.push_alerts_all_orgs()` — scheduler job `push_telegram_alerts` added, controlled by `TELEGRAM_ALERTS_ENABLED`.
- [x] Push delivery adapter: Telegram Bot API. CEO receives formatted alert immediately when anomaly detected. ✅ *(2026-05-19)*
  - Done: `TelegramService.send_message()` + `format_alert()` in `telegram_service.py`. Severity emoji: 🔴/🟠/🟡.
- [x] Alert deduplication: same anomaly not re-sent within configurable cooldown (default 4h). ✅ *(2026-05-19)*
  - Done: `TelegramAlertLog` model + Alembic migration `n4c5d6e7f8g9`. One row per `(org, alert_key)` tracks `last_sent_at`.
- [x] Alert severity tiers: 🔴 Critical, 🟠 High — only these trigger push alerts (medium findings appear in daily briefing only). ✅ *(2026-05-19)*
- [x] CEO can reply to a Telegram alert and the reply routes back into the AI manager. ✅ *(2026-05-19)*
  - Done: `POST /api/telegram/webhook` receives Telegram updates, routes CEO messages through `TelegramAlertService.route_ceo_message()` → `AIManagerService.answer()` → reply sent back.
  - Fixed: Telegram routing can call `AIManagerService.answer()` without an interactive `current_user`; the chat ID's delivery setting supplies the organization scope. Regression test added. ✅ *(2026-05-19 23:59 UTC)*
- [x] Alert delivery settings use existing per-org `AIWeeklyReportDeliverySetting.telegram_chat_ids`. ✅ *(2026-05-19)*
  - No new table needed — reuses the weekly report delivery setting rows already in place.

### 9.3 Daily CEO Briefing (Replace Weekly-Only Reports)

- [x] Daily morning briefing job (configurable time, default 08:00 local): generates ranked finding summary from `AIBriefingService`. ✅ *(2026-05-19)*
  - Done: `TelegramAlertService.send_daily_briefing_all_orgs()` — scheduler job `send_daily_briefing` controlled by `AI_DAILY_BRIEFING_ENABLED`.
- [x] Briefing delivered via Telegram to all orgs with Telegram chat IDs configured. ✅ *(2026-05-19)*
  - Done: `TelegramService.format_briefing()` formats top 8 findings with emoji, scope, and date label.
- [x] Briefing includes data freshness status via `data_trust_status` from `AIBriefingService`. ✅ *(2026-05-19)*
- [x] Weekly report remains for deeper narrative; daily briefing is the operational pulse. ✅ *(2026-05-19)*

### 9.4 Conversation Quality for a Non-Technical CEO

- [ ] System prompt rewritten to be CEO/owner-facing: no references to "projection facts", "cloud read models", or internal table names. Plain English: "your Kumasi branch", "Paracetamol", "last week's sales". *(2026-05-19)*
- [ ] LLM answer must always state the time window and branch scope it used so the CEO can verify the context. *(2026-05-19)*
- [ ] If data is stale or missing for a specific question, say so explicitly with how stale — not a silent zero. *(2026-05-19)*
- [ ] Add `POST /ai-manager/chat` parameter: `branch_name` filter (in addition to `branch_id`) so the CEO can ask "what's happening at Kumasi?" and the system resolves the branch. *(2026-05-19)*

---

## Phase E: Customer Retention Module (online_pos only)

> This phase covers the customer registration, digital receipts, health follow-up automation, and analytics features available in `online_pos` mode. Not applicable to village `local_pos` installs.

### E.1 Customer Registration & Database

- [x] `Customer` model with org/branch scoping, phone uniqueness, consent fields, soft-delete ✅ *(2026-05-28)*
- [x] `CustomerFollowUp` model: scheduled messages, delivery tracking, retry count, channel ✅ *(2026-05-28)*
- [x] Alembic migration `o5d6e7f8g9h0`: creates `customers`, `customer_follow_ups` tables; adds `customer_id` FK and `receipt_sent` flag to `sales` ✅ *(2026-05-28)*
- [x] `customer_id` (optional FK) linked to `Sale` at POS checkout ✅ *(2026-05-28)*

### E.2 Customer Consent & Data Protection

- [x] Consent captured at registration for SMS and WhatsApp separately (`granted` / `declined` / `pending`) ✅ *(2026-05-28)*
- [x] Receipt and follow-up dispatch check consent before sending — no messages sent without `granted` ✅ *(2026-05-28)*
- [x] `consent_recorded_at` timestamp recorded on all consent changes for audit trail ✅ *(2026-05-28)*
- [ ] Opt-out webhook handler to update consent on "STOP" reply — requires provider webhook setup *(deferred to provider integration)*

### E.3 SMS/WhatsApp Delivery

- [x] `MessageAdapter` abstract base with `send()`, `send_receipt()`, `send_follow_up()` ✅ *(2026-05-28)*
- [x] `StubAdapter`: default — logs messages, marks follow-ups as sent, no cost ✅ *(2026-05-28)*
- [x] `AfricasTalkingAdapter`: Ghana SMS via Africa's Talking API. Activated by `SMS_PROVIDER=africas_talking` + `SMS_USERNAME` + `SMS_API_KEY` ✅ *(2026-05-29)*
  - Ghana number normalisation (0244… → +233244…, E.164 passthrough)
  - statusCode 101/102 = sent/queued; other codes = failure
  - WhatsApp falls back to SMS with a warning log (AT has no native WA API yet)
  - Sender ID: configurable `SMS_SENDER_ID`, capped at 11 chars (AT Ghana requirement)
- [x] Hubtel adapter path wired in `get_adapter()` — set `SMS_PROVIDER=hubtel` + `SMS_CLIENT_ID` + `SMS_CLIENT_SECRET` + `SMS_FROM_NUMBER` ✅ *(2026-05-29)*
  - Requires `_hubtel_adapter.py` (interface defined, implementation to fill in on contract award)
- [x] All SMS config typed in `Settings` class: `SMS_PROVIDER`, `SMS_SENDER_ID`, `SMS_API_KEY`, `SMS_USERNAME`, `SMS_FROM_NUMBER`, `SMS_CLIENT_ID`, `SMS_CLIENT_SECRET` ✅ *(2026-05-29)*
- [x] Follow-up scheduling: `CUSTOMER_FOLLOWUP_DAYS` (default 3 days after purchase), `CUSTOMER_FOLLOWUP_HOUR` (default 10:00) ✅ *(2026-05-29)*
- [ ] **Production gate:** Set `SMS_PROVIDER` to `africas_talking` and provide real credentials before go-live. Verify with sandbox first.

### E.4 Retention Service & Scheduler

- [x] `CustomerRetentionService.dispatch_receipt()`: non-fatal; called after each sale commit in online_pos mode ✅ *(2026-05-28)*
- [x] `CustomerRetentionService.schedule_follow_up()`: creates PENDING follow-up record ✅ *(2026-05-28)*
- [x] `CustomerRetentionService.process_pending_follow_ups()`: processes overdue PENDING follow-ups ✅ *(2026-05-28)*
- [x] Hourly scheduler job `dispatch_customer_follow_ups` in `online_pos` mode only ✅ *(2026-05-28)*

### E.5 Frontend — Customer Module

- [x] `CustomerModal.tsx`: POS search (250ms debounce) + new registration + consent capture ✅ *(2026-05-28)*
- [x] `CustomersPage.tsx`: customer directory with profile drill-down, purchase count, follow-up history ✅ *(2026-05-28)*
- [x] `FollowUpDashboard.tsx`: operator view — status tiles, overdue alerts, sortable table ✅ *(2026-05-28)*
- [x] `CustomerAnalyticsPage.tsx`: 5 KPI cards, lifecycle funnel, consent panel, top customers, product affinity ✅ *(2026-05-29)*
- [x] Sidebar: Customers, Customer Analytics, Follow-ups — visible in `online_pos` mode only ✅ *(2026-05-29)*

### E.6 AI Integration

- [x] `get_customer_analytics` AI tool registered in `TOOL_SCHEMAS` ✅ *(2026-05-29)*
- [x] `_compose_answer()` keyword routing: customer/retention/churn/at-risk etc. queries answered deterministically ✅ *(2026-05-29)*
- [x] Telegram daily briefing includes retention block (total/new/repeat rate/at-risk/churned/follow-up stats) in `online_pos` mode ✅ *(2026-05-29)*

### E.7 Test Coverage

- [x] 21 tests in `test_customer_retention.py`: registration, consent, analytics service (7 scenarios), StubAdapter, get_adapter fallback, AT number normalisation (5 cases) ✅ *(2026-05-29)*
- [x] Full suite: **158 tests pass** *(2026-05-29)*

---

## Phase 10: Isolated Per-Tenant Architecture & Fleet Control Plane

> **Added:** 2026-06-06 UTC — supersedes the shared-database `online_pos` direction.
> **Revised:** 2026-06-07 UTC — incorporated architecture-review corrections (isolation wording, topology-before-PITR, PII/schema policy, break-glass hardening, non-blocking publish, canary migrations, global identifiers, hosted-offline limits; reordered so transactional correctness precedes migration/reporting/AI; verification tests promoted to P0 gates).
>
> **Goal:** unify city (hosted) and village (on-site) pharmacies onto **one tenancy model**: every pharmacy runs the *same single-tenant backend image* against *its own database*, and every install publishes events to *one central reporting/control-plane database* for the vendor dashboard and fleet AI. Stop maintaining the shared-DB `online_pos` model.
>
> ```
> City:    Hosted backend + tenant DB ─┐
> Village: Local backend + local DB  ──┼─> Central reporting DB ─> Vendor dashboard / fleet AI
>                                      └─> (break-glass support access)
> ```
>
> **Architecture decisions recorded:**
> - **One model, not two.** A city pharmacy is a village install that the vendor hosts. The existing sync outbox → projection → `cloud_reporting` → Clients page machinery is the foundation; the change is making *hosted* tenant backends publish events too.
> - **Operational-DB isolation is structural, not query-level.** Each tenant has its own operational database, so there is no `WHERE organization_id` to forget on the till path. This is *not* the same as "leakage is impossible": deployment misconfiguration (a backend pointed at the wrong `DATABASE_URL`), the central reporting DB, backups, and break-glass access remain real leak surfaces and must be controlled explicitly (see 10.5, 10.8).
> - **Two AIs, two sources.** The in-pharmacy **AI Manager** reads that tenant's **live operational tables**. **Fleet AI** and the vendor dashboard read the **central reporting DB** only.
> - **Complexity moves to automation (deploy-time, testable), not to every transactional request.** Correct trade-off at ~10 clients.
> - **Hosted clients trade offline resilience for real-time cloud features.** A hosted city pharmacy's backend *and* database are remote, so it cannot truly operate offline — its only buffer is the browser queue (`ONLINE-P1-01`), which must be hardened (10.9). Clients that need real offline operation use the village/local deployment, not hosted.
>
> **Honest scope correction (do not overclaim):** going single-tenant removes the *cross-pharmacy* dimension of `ONLINE-P0-01..05`, but it does **not** remove intra-tenant correctness work — **branch-level authorization, customer↔sale ownership, inventory stamping/integrity, and AI live-data sourcing still need fixing**. Those become ordinary single-tenant correctness instead of shared-DB breach risks, and per 10.1 they are fixed **before** any data migration, reporting, or AI is built on top.

### 10.0 Decision, Topology & Reconciliation

- [ ] **Choose provider, topology, and backup mechanism first** — this gates everything below. Decide between *one managed cluster with many databases* vs *separate instances/projects per tenant*, because **per-database point-in-time restore is not guaranteed when tenant databases share one managed server** (many providers do PITR at the instance level only). The recoverability promise in 10.3 depends on this choice. *(2026-06-07 UTC)*
- [x] Record the per-tenant + central-plane decision in `MEMORY.md` and supersede the shared-DB `online_pos` direction in decisions **3.30**, **3.32**, and **3.33**. ✅ *(2026-06-07 07:31 UTC)*
- [x] Reframe `ONLINE-P0-01..05` in `MEMORY.md`: cross-pharmacy isolation is addressed by the architecture; remaining items are intra-tenant correctness work (branch auth, customer ownership, inventory integrity, AI live-sourcing). ✅ *(2026-06-07 07:31 UTC)*
- [x] Confirm the initial target scale of roughly 10 clients. **A separate database per client is the standard for every client.** A separate *cluster/project/instance* is reserved for a future enterprise client with contractual physical-isolation, residency, or SLA requirements. ✅ *(2026-06-07 07:31 UTC)*

### 10.1 P0 Transactional Correctness — FIX BEFORE MIGRATION, REPORTING, OR AI

> Migrating data or building central reporting/AI on top of integrity bugs propagates corruption into the central DB and AI answers. This is the first build step after the decision, per CLAUDE.md priority #1 (data integrity).

- [x] Customer↔sale ownership validated (a sale links only to an active customer in the same tenant/branch, before any stock mutation). ✅ *(2026-06-07 07:31 UTC)*
- [ ] Inventory stamping/integrity consistent across every write path (`ProductBatch`, all `InventoryMovement` sources). *(2026-06-07 UTC)*
- [ ] Branch-level authorization enforced within a tenant (a branch user sees only permitted branch data). *(2026-06-07 UTC)*

### 10.2 P0 Provisioning, Identifiers & Unified Runtime

- [ ] **Define one operational POS mode** with deployment feature flags for *hosted* vs *offline* (replaces the `local_pos` / `online_pos` split). Hosted and offline differ only by config, not by tenancy model. *(2026-06-06 UTC)*
  - Flags cover: hosted scheduling, outbox publishing target, customer-retention features, receipt/follow-up dispatch.
- [ ] **Globally stable tenant / deployment / device identifiers.** `event_id` is already a UUID and ingestion is idempotent on `(source_device_id, local_sequence_number)`, but `aggregate_id` is a local integer and org/branch/device IDs must be **allocated by the control plane, never local autoincrement**, so facts from separate tenant databases cannot collide in the central DB. *(2026-06-07 UTC)*
- [ ] **Tenant provisioning tooling:** allocate global IDs → create tenant database → run migrations → seed admin user → register in control-plane → issue per-tenant secrets/token. Repeatable script/IaC. *(2026-06-06 UTC)*
- [ ] **Per-tenant secrets management:** each backend gets its own `DATABASE_URL`, `SECRET_KEY`, SMS keys, and central-publish token, injected at deploy and never committed (extend the per-device sync-token pattern from decision 3.12). *(2026-06-06 UTC)*

### 10.3 P0 Backup / Restore Proof (depends on 10.0 topology)

- [ ] **Encrypted per-tenant backups** automated for every hosted tenant database. *(2026-06-06 UTC)*
- [ ] **Rehearsed single-tenant restore drill** — prove one pharmacy can be restored to a point in time without touching any other tenant. If tenant databases share one managed server, this requires **logical per-DB backups (`pg_dump`)**, not instance-level PITR. A restore procedure on paper does not count. *(2026-06-07 UTC)*
- [ ] Per-tenant logical export ("give me my data" / clean offboarding). *(2026-06-06 UTC)*

### 10.4 P0 Canary Migration Tooling

- [ ] **Migrate-all-tenants tooling:** run Alembic migrations across every tenant database in one command, with per-tenant success/failure reporting. *(2026-06-06 UTC)*
- [ ] **Canary migrations:** migrate one tenant first and verify before fleet-wide rollout. *(2026-06-07 UTC)*
- [ ] **Backward-compatible (expand/contract) migration rules** so old and new app versions both work during a staged rollout. *(2026-06-07 UTC)*
- [ ] **Rollback handling** for a failed tenant migration (forward-fix or revert path defined and tested). *(2026-06-07 UTC)*

### 10.5 P0 Outbox Publishing & Central Ingestion (tests are release gates)

- [ ] **Central/reporting failure must NEVER block a POS transaction.** Hosted backends publish via the existing async transactional-outbox + background delivery (already true for village installs — preserve it; do not introduce a synchronous publish in the sale path). *(2026-06-07 UTC)*
- [ ] **Enable reliable outbox publishing from hosted tenant backends** (today only village/local installs publish; hosted `online_pos` writes direct and skips the outbox). *(2026-06-06 UTC)*
- [ ] **Central event contract: explicit, versioned schemas + retention + PII minimization.** `schema_version` already exists on sync events; add explicit per-event schema definitions, a retention policy, and **PII restrictions — do not centrally publish customer medical/health-follow-up details or unrestricted audit payloads.** Publish aggregates/IDs, not sensitive customer content. *(2026-06-07 UTC)*
- [ ] Central reporting DB ingests published events from *all* tenants (sales summaries, inventory snapshots/movements, audit *metadata*, login/security events, device + backend heartbeat, backup/migration status, AI findings, errors/failed jobs). *(2026-06-06 UTC)*
- [ ] Vendor dashboard reads **only** the central DB (no per-request fan-out across tenant databases). *(2026-06-06 UTC)*
- [ ] **P0 release gate — event idempotency tests** for central ingestion (same `event_id` + same `payload_hash` accepted, different hash rejected). *(2026-06-07 UTC)*
- [ ] **P0 release gate — central reconciliation tests** (central facts match per-tenant source data). *(2026-06-07 UTC)*
- [ ] **P0 release gate — fleet rollout test** (a code update + `migrate-all` succeeds across N tenant backends/DBs). *(2026-06-07 UTC)*

### 10.6 P0 Migrate Existing Tenant Data (after 10.1 correctness + tooling)

- [ ] **Migrate the existing shared Supabase data into the first isolated tenant database — do this while effectively single-tenant** (cheapest possible blast radius before client #2), only after transactional correctness (10.1) so corrupt data is not propagated. Include a rehearsed cutover + rollback step. *(2026-06-07 UTC)*

### 10.7 P0 Tenant AI Live-Data Sourcing

- [ ] **In-pharmacy AI Manager reads the tenant's live operational tables**, not the central projection tables (resolves the `online_pos` half of `ONLINE-P0-05`). *(2026-06-06 UTC)*
  - Affects: `ai_manager_service.py`, `ai_briefing_service.py`, `ai_weekly_report_service.py` (currently hard-wired to `Cloud*` services).
- [ ] **Fleet AI reads the central reporting DB** for cross-pharmacy intelligence; the two AI data sources are explicitly separated. *(2026-06-06 UTC)*

### 10.8 P0 Control Plane & Break-Glass Support Access

- [ ] **Central control-plane registry** of tenants/deployments (org, branch, deployment URL, install date, lifecycle state, current secret/token age). *(2026-06-06 UTC)*
- [ ] **Break-glass support access — prefer application-level, time-limited support sessions over direct database access.** Require MFA and an approval step, default to read-only, support explicit revocation, and write a full audit log (explicit reason + expiry). *(2026-06-07 UTC)*
- [ ] Cross-tenant safety test: a request authenticated for tenant A cannot reach tenant B's deployment/data. *(2026-06-07 UTC)*

### 10.9 P0 Hosted-Client Offline Resilience

- [ ] **Harden the hosted-client offline buffer** — the IndexedDB sale queue (`ONLINE-P1-01`) has no durable invoice/receipt ledger and failed flushes can be cleared from the UI. Database isolation does **not** fix this. Add a durable receipt/invoice ledger and prevent silent loss on failed flush. *(2026-06-07 UTC)*
- [ ] Document the offline limit explicitly: hosted clients get a short network-drop buffer only; clients needing true offline operation deploy the village/local model. *(2026-06-07 UTC)*

### 10.10 P0 Gradual Removal of Shared-DB `online_pos` (last)

- [ ] Migrate, in order, onto the unified single-tenant runtime — **do not rip out `online_pos` in one shot**: (1) customer-retention features, (2) hosted scheduling, (3) outbox publishing, (4) tenant AI. *(2026-06-06 UTC)*
- [ ] Retire the `online_pos` shared-DB direct-write code paths and tenant-scope guards once all features run on the unified runtime. *(2026-06-06 UTC)*

### 10.11 Sequencing (recommended order)

> 10.0 decision + topology → 10.1 transactional correctness → 10.2 provisioning + global identifiers + unified runtime → 10.3 backup/restore proof → 10.4 canary migration tooling → 10.5 outbox + central ingestion + gate tests → 10.6 migrate existing tenant data → 10.7 live tenant AI → 10.8 control plane + break-glass → 10.9 hosted-offline hardening → 10.10 remove shared `online_pos` paths.

---

## Sign-Off

| Role | Name | Date | Approved |
| ---- | ---- | ---- | -------- |
| Technical Lead | | | ☐ |
| Pharmacy Operations | | | ☐ |
| System Admin | | | ☐ |
