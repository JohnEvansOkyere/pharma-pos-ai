# Online-First POS Architecture (`online_pos` Mode)

**Document type:** Technical reference  
**Status:** SUPERSEDED on 2026-06-07
**Last updated:** 2026-05-28  
**Author:** Antigravity agent  
**Audience:** Any developer or agent continuing work on this system

> This document describes the retired shared-Supabase `online_pos` design.
> Do not use it as current implementation guidance. Hosted pharmacies now use
> `APP_MODE=operational_pos`, `POS_DEPLOYMENT_PROFILE=hosted`, a dedicated
> Render backend/database, and the transactional outbox. See
> `docs/architecture/unified-operational-runtime.md`.

---

## 1. Why This Exists

The original system was built strictly offline-first (`local_pos`): a PostgreSQL database runs on the pharmacy's own machine, and data syncs to a central Supabase cloud periodically via an outbox queue. This is intentional for village/rural pharmacies with unreliable internet.

City pharmacies asked for something different:
- Always-connected, cloud-native POS (writes go directly to Supabase)
- Customer retention: registration, digital receipts, health follow-up messages
- Cloud dashboard accessible from the POS machine without separate login
- Still functions if internet drops temporarily (short-term resilience)

The solution is a **third app mode** (`online_pos`) added to the existing mode system, sharing the same codebase. No separate fork exists.

---

## 2. The Three App Modes

The system can run in exactly one of three modes, set via `APP_MODE` in the backend `.env` file and `VITE_APP_MODE` in the frontend `.env`:

| Mode | Who uses it | Database | Sync outbox | POS writes | Cloud dashboard |
|---|---|---|---|---|---|
| `local_pos` | Village pharmacy workstation | Local PostgreSQL | ✅ Active | ✅ Yes | Optional |
| `online_pos` | City pharmacy workstation | Supabase (cloud) | ❌ Skipped | ✅ Yes | ✅ Yes |
| `cloud_reporting` | CEO/vendor portal | Supabase (cloud) | ❌ N/A | ❌ Blocked | ✅ Yes |

The key behavioral differences between `local_pos` and `online_pos`:

| Concern | `local_pos` | `online_pos` |
|---|---|---|
| Sync outbox | Every write goes to local outbox | Outbox skipped — data already in cloud |
| Tenant stamping | Via `CLOUD_SYNC_ORGANIZATION_ID` env var | Stamped from authenticated user's `organization_id` |
| Offline behavior | Always online (local DB) | Network loss → IndexedDB queue → auto-flush |
| Scheduled jobs | Upload, heartbeat, catalog snapshot | All sync jobs skipped |
| Frontend default route | Admin → `/dashboard`, cashier → `/pos` | Admin/manager → `/cloud-dashboard`, cashier → `/pos` |

---

## 3. Backend Changes

### 3.1 `app/core/app_mode.py`

The single source of truth for mode logic. All other files import from here.

**New constants:**
```python
ONLINE_POS_MODE = "online_pos"
VALID_APP_MODES = {"local_pos", "online_pos", "cloud_reporting"}
```

**New helper functions:**
```python
def is_online_pos_mode(value: str | None) -> bool:
    """True when APP_MODE == 'online_pos'."""

def is_pos_mode(value: str | None) -> bool:
    """True when POS writes are allowed (local_pos or online_pos)."""

def apply_tenant_scope(obj: Any, current_user: User, *, app_mode: str | None) -> None:
    """Stamps organization_id and branch_id from the authenticated user
    onto any ORM object. No-op in local_pos mode."""
```

**`is_local_operational_write` (existing, unchanged in logic):**  
Only blocks writes in `cloud_reporting` mode. Both `local_pos` and `online_pos` pass through.

**`apply_tenant_scope` — important details:**
- Called **after `db.flush()`** (so the row has an id) but **before `db.commit()`**
- In `local_pos` mode: complete no-op, existing behavior is preserved
- In `online_pos` mode: sets `obj.organization_id = current_user.organization_id` and `obj.branch_id = current_user.branch_id` if they are not None
- This is how city pharmacies sharing the same Supabase instance stay isolated from each other

### 3.2 `app/core/config.py`

- `APP_MODE` field comment updated: `# local_pos, online_pos, or cloud_reporting`
- Validator accepts all three values
- Error message updated

### 3.3 `app/services/sync_outbox_service.py`

Added `_should_record()` method:

```python
@staticmethod
def _should_record() -> bool:
    return not is_online_pos_mode(settings.APP_MODE)
```

`record_event()` now short-circuits immediately when `_should_record()` returns False, returning `None` instead of `SyncEvent`. All callers that receive the return value must accept `Optional[SyncEvent]` — this is the updated type signature.

**Why:** In `online_pos` mode the write goes directly to Supabase. Generating a local outbox event would be meaningless (there is no local-to-cloud sync step) and would accumulate noise in the database.

### 3.4 `app/services/scheduler.py`

Two guard conditions added:

```python
# Sync jobs — skipped in online_pos
if settings.CLOUD_SYNC_ENABLED and not is_online_pos_mode(settings.APP_MODE):
    # heartbeat, upload_sync_events, nightly_cloud_catalog_sync

# Cloud projection — skipped in online_pos
if settings.CLOUD_PROJECTION_ENABLED and not is_online_pos_mode(settings.APP_MODE):
    # project_cloud_events
```

**Why:** `online_pos` writes go directly to the main database tables. There are no sync events to upload or project.

### 3.5 POS Write Endpoints

Three endpoints were updated:

#### `app/api/endpoints/sales.py`
- Added imports: `apply_tenant_scope`, `is_online_pos_mode`, `settings`
- `create_sale`: calls `apply_tenant_scope(db_sale, current_user, app_mode=settings.APP_MODE)` after `db.flush()`
- `list_sales`: filters by `Sale.organization_id == current_user.organization_id` when in `online_pos` mode and user has an org

#### `app/api/endpoints/products.py`
- Added same imports
- `create_product`: calls `apply_tenant_scope(db_product, current_user, app_mode=settings.APP_MODE)` after `db.flush()`
- `list_products`, `list_products_catalog`, `search_products`: all filtered by org in `online_pos` mode

#### `app/api/endpoints/stock_adjustments.py`
- Added same imports
- `create_stock_adjustment`: calls `apply_tenant_scope(db_adjustment, current_user, app_mode=settings.APP_MODE)` after `db.flush()`
- `list_stock_adjustments`: filtered by org in `online_pos` mode

---

## 4. Frontend Changes

### 4.1 `src/config/appMode.ts`

The central frontend mode file. All components import from here — never read `import.meta.env` directly.

```typescript
export const APP_MODE = (import.meta.env.VITE_APP_MODE || 'local_pos').trim().toLowerCase()

export const isCloudReportingMode = APP_MODE === 'cloud_reporting'
export const isOnlinePosMode      = APP_MODE === 'online_pos'
export const isLocalPosMode       = APP_MODE === 'local_pos'
export const isPosMode            = isLocalPosMode || isOnlinePosMode

export function getDefaultAuthenticatedPath(user?) {
  // cloud_reporting → /clients or /cloud-dashboard
  // online_pos → admin/manager go to /cloud-dashboard, cashier to /pos
  // local_pos → admin to /dashboard, others to /pos
}
```

### 4.2 `src/App.tsx`

Route gating now uses `isPosMode` instead of `!isCloudReportingMode`. This means `online_pos` users see all POS routes (products, POS, sales, stock-adjustments, suppliers, notifications, settings) **and** the cloud dashboard.

### 4.3 `src/components/layout/Sidebar.tsx`

- Imports `isOnlinePosMode`, `isPosMode`
- In `online_pos` mode: POS items AND cloud dashboard item are visible
- Footer shows: `Cloud` / `Online` / `Local` depending on mode

### 4.4 `src/components/layout/MainLayout.tsx`

Wires the `OfflineBanner` component between the header and the main content area. The banner is always mounted but renders nothing when mode is `local_pos` or when the device is online.

```tsx
const onlineStatus = useOnlineStatus()
// ...
<OfflineBanner onlineStatus={onlineStatus} />
```

---

## 5. Offline Fallback Queue (Phase B)

This is the core resilience feature for `online_pos` city pharmacies.

### 5.1 Architecture

```
Internet ──► API ──► Supabase DB
   ↑
Browser (online_pos frontend)
   │                     │ (offline)
   │                     ▼
   │              IndexedDB Queue
   │             (offlineQueue.ts)
   │                     │
   └─────────────────────┘
        (on reconnect: auto-flush)
```

### 5.2 `src/services/offlineQueue.ts`

IndexedDB database: `pharma_offline_queue`  
Object store: `pending_sales`  
Key path: `id` (autoIncrement)  
Indexes: `status`, `queuedAt`

**API:**

| Function | Purpose |
|---|---|
| `enqueue(payload)` | Add a sale payload to the queue. Returns the new item ID. |
| `list()` | Return all items ordered by `queuedAt` (FIFO). |
| `pendingCount()` | Count of items with `status === 'pending'`. |
| `flush(postSale, onProgress?)` | Drain pending items. Calls `postSale()` for each. On failure, increments `attempts`. After 3 failures, marks item `'failed'` and skips it. Returns `{ flushed, failed, remaining }`. |
| `clearFailed()` | Remove all `'failed'` items (operator cleanup). |

**Item shape:**
```typescript
interface QueuedSale {
  id?: number          // auto-assigned
  payload: Record<string, unknown>
  queuedAt: string    // ISO timestamp
  attempts: number
  status: 'pending' | 'failed'
  lastError?: string
}
```

**Retry policy:** Up to 3 attempts per item. If all 3 fail, item is marked `failed` and skipped. The `OfflineBanner` shows a count of failed items and provides a "Clear failed" button. Failed items do not block other items.

### 5.3 `src/hooks/useOnlineStatus.ts`

Returns `{ isOnline, isChecking, lastChecked, recheckNow }`.

- In `local_pos` mode: always returns `{ isOnline: true }` — no-op
- In `online_pos` mode:
  - Checks `navigator.onLine` immediately
  - Polls API heartbeat every **15 seconds** with an **8-second timeout**
  - Heartbeat URL: `GET /api/auth/heartbeat` (with auth header)
  - Fallback URL: `GET /api/products/catalog?limit=1` (if heartbeat endpoint missing)
  - Responds to `online`/`offline` browser events for fast reaction

### 5.4 `src/components/layout/OfflineBanner.tsx`

Mounted in `MainLayout` — visible across all pages.

**States:**

| State | Trigger | Color | Content |
|---|---|---|---|
| `hidden` | Online, queue empty | — | Not rendered |
| `offline` | `isOnline === false` | Red | Queue count, "Check now" button |
| `flushing` | Back online, queue > 0 | Amber | "Syncing N queued sales…" |
| `flushed` | Flush complete | Green | "N sales synced. / N failed." |

**Flush trigger:** When `isOnline` transitions from `false` to `true`, the banner automatically calls `flush(api.createSale)`. No user action required.

### 5.5 `src/pages/POSPage.tsx`

Two additions:

1. **Offline badge** — shown inline under the "Pharmacy POS" title when `isOnlinePosMode && !isOnline`:
   ```
   ● OFFLINE — QUEUING SALES
   ```

2. **Sale queuing path** — in `handleCompleteSale()`, before the normal API call:
   ```typescript
   if (isOnlinePosMode && !isOnline) {
     await enqueue(payload)
     toast.success('Offline — sale queued. Will sync when reconnected.')
     resetCheckoutState()
     return   // <-- does NOT call api.createSale()
   }
   // falls through to normal api.createSale() if online
   ```

**Important:** When offline, stock levels in the UI are NOT decremented locally. This is a known limitation — the cashier can oversell if many sales are queued offline. A future improvement would track provisional stock locally. For now, the tradeoff is acceptable for city pharmacies where connectivity is usually brief.

---

## 6. Tenant Isolation Strategy

In `online_pos` mode, multiple city pharmacies share the same Supabase instance. Isolation works at two levels:

### 6.1 Row-Level: `apply_tenant_scope()`

Every new record gets `organization_id` and `branch_id` stamped from `current_user` at creation time. This happens server-side, cannot be bypassed by the client.

```
User logs in → has organization_id = 7, branch_id = 2
↓
create_sale() → db_sale.organization_id = 7, db_sale.branch_id = 2
               db_sale.user_id = current_user.id
```

### 6.2 Query-Level: Org-Scoped Reads

List/search endpoints filter by `organization_id` in `online_pos` mode:

```python
if is_online_pos_mode(settings.APP_MODE) and current_user.organization_id is not None:
    query = query.filter(Sale.organization_id == current_user.organization_id)
```

This means pharmacists can only see their own organization's products, sales, and adjustments.

### 6.3 Database-Level: Supabase RLS

Supabase Row Level Security (RLS) policies should be configured as a defense-in-depth layer. The application-level scoping above is the primary guard. RLS policies are the backup. Both must be maintained.

### 6.4 Vendor/Superadmin Access

A vendor admin user (`role=admin`, `organization_id=NULL`) can read across all organizations. This is used by the `cloud_reporting` portal and is guarded by `get_vendor_admin()` in the auth dependencies.

---

## 7. Deployment: Setting Up a New City Pharmacy

### Backend `.env` (city pharmacy install)
```env
APP_MODE=online_pos
DATABASE_URL=postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres

# Sync outbox is not used in online_pos — these can be left at defaults
CLOUD_SYNC_ENABLED=false
CLOUD_PROJECTION_ENABLED=false
```

### Frontend `.env`
```env
VITE_APP_MODE=online_pos
VITE_API_URL=https://<city-pharmacy-backend>.onrender.com/api
```

### User provisioning
City pharmacy users must be created by the vendor admin through the `/admin/organizations` + `/users` endpoints. Self-registration is not available. Each user must have:
- `organization_id` — the pharmacy's organization record
- `branch_id` — the branch they work at
- `role` — `cashier`, `manager`, or `admin`

---

## 8. What Has NOT Been Implemented Yet

### Phase A — remaining
- [ ] **Organization_id scoping** is implemented for `sales`, `products`, and `stock_adjustments`. Other endpoints (categories, suppliers, notifications) are **not yet scoped** — they currently return all records regardless of org. This is acceptable in the short term since these are admin-managed catalog items, but should be scoped before production.
- [ ] **End-to-end Supabase integration test** — needs a provisioned Supabase project

### Phase B — remaining
- [ ] **Max offline window** — city pharmacies should eventually be forced to reconnect after N hours to prevent indefinite queuing. The timeout value and behavior (warn vs. force logout) are not yet defined or implemented.
- [ ] **Stock level pessimism** — the UI does not decrement stock locally when a sale is queued offline. A cashier could oversell.
- [ ] **Offline queue for non-sale writes** — currently only sales go through the queue. Product updates, stock adjustments, etc. will fail when offline. A future phase should wrap all mutation calls through the queue.

### Phase C — Customer Retention (not started)
- Customer model + migration
- Customer registration in POS
- Customer ID linked to sales
- SMS/WhatsApp receipt delivery
- Health follow-up scheduler

### Phase D — Customer Analytics (not started)
- Retention metrics, churn, product affinity
- Customer intelligence in AI briefings

---

## 9. File Map

```
backend/
  app/core/
    app_mode.py          ← VALID_APP_MODES, is_online_pos_mode(), apply_tenant_scope()
    config.py            ← APP_MODE validator (accepts all 3 modes)
  app/services/
    sync_outbox_service.py  ← _should_record() short-circuit in online_pos
    scheduler.py            ← sync jobs skipped in online_pos
  app/api/endpoints/
    sales.py             ← apply_tenant_scope + org-scoped list
    products.py          ← apply_tenant_scope + org-scoped list/catalog/search
    stock_adjustments.py ← apply_tenant_scope + org-scoped list
  tests/
    test_app_mode.py     ← 8 tests covering all 3 modes

frontend/src/
  config/
    appMode.ts           ← APP_MODE, isOnlinePosMode, isPosMode, getDefaultAuthenticatedPath
  hooks/
    useOnlineStatus.ts   ← navigator.onLine + heartbeat hook
  services/
    offlineQueue.ts      ← IndexedDB queue (enqueue, flush, clearFailed)
  components/layout/
    MainLayout.tsx        ← mounts OfflineBanner
    OfflineBanner.tsx     ← offline/flushing/success banner
    Sidebar.tsx           ← mode-aware nav items + footer label
  pages/
    POSPage.tsx           ← queues sales when offline; offline badge
  App.tsx                 ← isPosMode route gating

docs/
  DUAL_MODE_DEPLOYMENT_PLAN.md    ← roadmap and phase checklist
  ONLINE_FIRST_ARCHITECTURE.md   ← this document
```

---

## 10. Testing the Online POS Mode

### Backend: run `test_app_mode.py`
```bash
cd backend
python -m pytest tests/test_app_mode.py -v
```
Covers: normalize, is_online_pos_mode, is_pos_mode, write guard for all 3 modes.

### Backend: all tests
```bash
python -m pytest tests/ -v
# Expected: 137 passed, 0 failed
```

### Frontend: TypeScript check
```bash
cd frontend
npx tsc --noEmit
# Expected: no output (exit 0)
```

### Manual: simulating offline in a browser
1. Set `VITE_APP_MODE=online_pos`, start the dev server
2. Open DevTools → Network → set to "Offline"
3. Complete a sale in the POS → toast should say "Offline — sale queued"
4. Switch network back to "Online"
5. Within 15 seconds, the OfflineBanner should appear amber ("syncing…") then green ("N sales synced")
6. Verify the sale appears in `/sales`

---

## 11. Key Design Decisions

| Decision | Rationale |
|---|---|
| Single codebase, mode flag — not a fork | Easier to maintain; village and city pharmacies diverge only in config |
| Sync outbox skipped (not just unused) in online_pos | Avoids accumulating meaningless local events; keeps DB clean |
| Tenant stamping server-side from JWT user | Client cannot forge organization_id; consistent with existing auth model |
| IndexedDB for offline queue | Browser-native, no extra library, survives page reload, persistent across sessions |
| Heartbeat every 15s with 8s timeout | Fast enough to detect drops; not so fast as to spam the server |
| Flush on reconnect — automatic, no user action | City pharmacist should not have to think about queued sales |
| Failed items marked, not deleted | Operator can inspect and clear; prevents data loss |
| Offline queue covers sales only (Phase B) | Sales are the most critical write; other writes are lower risk |
