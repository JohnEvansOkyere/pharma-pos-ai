# Frontend Audit Report

## Scope

Audit target: React/Vite frontend for an offline-first pharmacy POS deployment.

Focus areas:
- correctness of UI-to-API integration
- offline behavior
- operator workflow suitability
- deployment readiness on local pharmacy machines

Verification performed:
- source review across app shell, pages, stores, API client, layout, and build config
- `npm run build` completed successfully
- no frontend tests were found

## Executive Summary

The frontend is visually usable as a prototype, but it is not yet a trustworthy offline pharmacy client.

The main issues are:
- "offline-capable" is overstated; the app still depends almost entirely on live API calls
- PWA configuration exists, but practical offline data behavior is not implemented
- several flows are demo-quality or incomplete
- the dashboard mixes live data with mocked metrics

Recommendation: do not market the frontend as offline-ready for pharmacy operations yet.

## Rating

- Overall readiness: **High Risk**
- Market/deployment recommendation: **Not ready for real-world pharmacy rollout**

## Findings

### 1. High: Offline support is mostly branding, not working business functionality

Evidence:
- `frontend/src/services/api.ts:8-304`
- `frontend/src/stores/authStore.ts:26-89`
- `frontend/vite.config.ts:10-52`
- repo-wide search found no IndexedDB/localforage/offline queue implementation

Details:
- All business data is fetched from the backend over HTTP.
- Only token/user/theme are persisted locally in `localStorage`.
- There is no offline data store for products, sales, suppliers, notifications, or queued transactions.
- There is no sync engine for reconnect behavior.

Impact:
- If the local backend is unavailable, the UI cannot continue normal pharmacy operations.
- This is not true offline-first behavior; it is local-network dependency.

Required action:
- Decide the actual architecture:
  - local backend required at all times, or
  - true offline-first frontend with durable local storage and sync
- Do not market this as offline-capable until that decision is implemented.

### 2. High: PWA runtime caching is configured incorrectly for the app's real API path

Evidence:
- `frontend/vite.config.ts:33-50`
- `frontend/src/services/api.ts:8-16`

Details:
- The frontend calls `/api` by default.
- Workbox runtime caching only matches `https://api.*`.
- In production, this means the actual local `/api` traffic is not covered by the configured runtime cache rule.

Impact:
- The app may precache static assets but still fail hard for live business requests when connectivity to the local API fails.
- This widens the gap between claimed and actual offline behavior.

Required action:
- Align caching rules with the real API base path.
- More importantly, pair caching with durable offline data semantics, not just request caching.

### 3. High: Login flow sends non-admins to a route they cannot access

Evidence:
- `frontend/src/pages/LoginPage.tsx:18-23`
- `frontend/src/App.tsx:30-58`
- `frontend/src/App.tsx:91-109`

Details:
- After login, all users are navigated to `/dashboard`.
- Non-admin users are not allowed to access the dashboard and are redirected to `/pos`.

Impact:
- This causes avoidable redirect churn on every cashier or manager login.
- It signals weak workflow design for front-desk operators.

Required action:
- Route users directly by role after login.

### 4. High: Dashboard is partially demo logic, not production reporting

Evidence:
- `frontend/src/pages/DashboardPage.tsx:117-127`
- `frontend/src/pages/DashboardPage.tsx:157-161`

Details:
- The dashboard loads many endpoints in a single `Promise.all`.
- Growth indicators are hard-coded mock values.

Impact:
- One failing endpoint can degrade the entire dashboard load path.
- Mock business metrics reduce trust and are not acceptable in a marketed product.

Required action:
- Remove mocked KPIs.
- Load dashboard widgets independently with partial-failure handling.

### 5. Medium: Notification polling assumes a continuously reachable backend

Evidence:
- `frontend/src/components/layout/Header.tsx:14-29`

Details:
- The header polls unread counts every 60 seconds.

Impact:
- In an offline/local deployment, repeated failed polls create noise and unnecessary load.
- It also hides the deeper issue that notifications are not locally available when the API is unavailable.

Required action:
- Make polling connectivity-aware or move to push/local event refresh within the local deployment model.

### 6. Medium: Suppliers page is incomplete

Evidence:
- `frontend/src/pages/SuppliersPage.tsx:22-52`

Details:
- Suppliers can be listed, but the "Add Supplier" button has no behavior.
- No edit/delete flow is implemented here.

Impact:
- Supplier management is not production-complete.

Required action:
- Finish CRUD workflow or hide the control until complete.

### 7. Medium: Product creation uses two-step writes without UX rollback strategy

Evidence:
- `frontend/src/pages/ProductsPage.tsx:120-136`

Details:
- Product creation succeeds first.
- Initial batch creation is a second call.
- If batch creation fails, the product remains created without its intended opening stock.

Impact:
- Operators can create partial inventory records by accident.
- This is especially risky during onboarding or stock intake.

Required action:
- Move this to one backend transaction or add explicit rollback/repair handling in the UI.

### 8. Medium: Auth state is thin and not resilient

Evidence:
- `frontend/src/stores/authStore.ts:26-89`
- `frontend/src/services/api.ts:40-57`

Details:
- Auth relies on `localStorage` and a live `/auth/me` call.
- A transient backend failure is treated like session expiry.

Impact:
- Local deployment hiccups can log users out unnecessarily.
- That is disruptive on point-of-sale terminals.

Required action:
- Distinguish connectivity failures from authentication failures.

### 9. Medium: The production bundle is large for a pharmacy workstation app

Evidence:
- `npm run build` produced `dist/assets/index-*.js` at about `698 kB` before gzip

Impact:
- Slower startup on low-spec hardware.
- Less responsive experience on older pharmacy machines.

Required action:
- Split dashboard/reporting code from POS-critical routes.
- Prioritize fast boot for `/pos`.

### 10. Medium: Demo credentials and "offline ready" language remain visible in the live UI

Evidence:
- `frontend/src/pages/LoginPage.tsx:86-102`
- `frontend/src/components/layout/Sidebar.tsx` footer currently says `Offline Ready`

Impact:
- This is not acceptable in a commercial release.
- It creates legal and reputational risk if the product does not actually meet the stated capability.

Required action:
- Remove demo credentials and marketing claims from the release build.

## Offline Deployment Assessment

At the moment, the frontend should be described as:

- a browser client for a locally hosted backend, not
- a true offline-first pharmacy application

What is present:
- PWA build tooling
- service-worker generation during production build
- static asset precaching

What is missing:
- durable local operational data store
- offline transaction queue
- conflict resolution or sync recovery
- local-first product/sales browsing
- operator-safe degraded-mode behavior

## Strengths

- Build passes successfully
- layout and route organization are understandable
- core screens for login, products, POS, sales, and settings already exist
- the UI is serviceable as a starting point for a local pharmacy workstation app

## Recommended Release Gate

Minimum frontend gate before selling to pharmacies:

1. define the real offline model and implement it honestly
2. fix API caching assumptions and degraded-mode behavior
3. remove mock metrics and incomplete controls
4. make POS and login flows role-aware and resilient
5. add automated UI/API integration tests for core workflows

## Final Verdict

The frontend can become a good local pharmacy client, but today it is still prototype-grade. The biggest mismatch is that the UI presents itself as offline-ready while the underlying behavior still depends heavily on live API access.
