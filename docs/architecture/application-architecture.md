# Application Architecture

## Backend

The backend is a FastAPI application mounted under `/api`.

Important paths:

- `backend/app/main.py`: FastAPI app startup, CORS, scheduler lifecycle.
- `backend/app/api/__init__.py`: router composition.
- `backend/app/api/endpoints`: HTTP route handlers.
- `backend/app/api/dependencies/auth.py`: authentication, role checks, permission checks, tenant scoping.
- `backend/app/models`: SQLAlchemy tables.
- `backend/app/schemas`: Pydantic request/response contracts.
- `backend/app/services`: business logic and cross-route services.
- `backend/alembic/versions`: migration history.

Main routers:

- `/auth`: login and current-user identity.
- `/users`: admin-controlled user management.
- `/products`: products, batches, product catalog, receive stock.
- `/sales`: POS sales, sale list, sale summaries, voids, refunds, closeout reporting.
- `/stock-adjustments`: manual stock adjustments and write-offs.
- `/stock-takes`: draft and completed stock takes.
- `/suppliers`, `/categories`: master data.
- `/dashboard`, `/insights`, `/notifications`: local operational reporting.
- `/sync`: cloud ingestion and projection operations.
- `/cloud-reports`: cloud reporting, reconciliation, and repair workflow.
- `/ai-manager`: AI chat, weekly reports, delivery settings, provider policy.
- `/system`: backups, diagnostics, sync status, audit logs.

## Frontend

The frontend is a React 18 + TypeScript + Vite application.

Important paths:

- `frontend/src/App.tsx`: route protection and page routing.
- `frontend/src/services/api.ts`: Axios API client and auth/error interceptors.
- `frontend/src/stores/authStore.ts`: persisted JWT/user state.
- `frontend/src/stores/cartStore.ts`: POS cart state.
- `frontend/src/pages`: route pages.
- `frontend/src/components/layout`: sidebar, header, layout shell.
- `frontend/src/styles/index.css`: Tailwind and global styling.

Main pages:

- `/login`: authentication.
- `/pos`: cashier workflow and sales entry.
- `/products`: product, batch, stock receiving workflow.
- `/sales`: sales review and sale operations.
- `/stock-adjustments`: manager/admin stock adjustments.
- `/dashboard`: local admin dashboard.
- `/cloud-dashboard`: manager/admin cloud reporting, AI assistant, weekly reports, reconciliation.
- `/audit-logs`: admin audit review/export.
- `/notifications`: expiry and stock alerts.
- `/settings`: diagnostics, backups, user management, operational settings.

## Auth And Routing Model

Frontend route guards:

- authenticated users can access the main layout
- admin-only routes include local dashboard and audit logs
- admin or manager routes include cloud dashboard, stock adjustments, and settings

Backend enforcement is the actual security boundary:

- roles: `admin`, `manager`, `cashier`
- granular permissions: product management, user management, report viewing, sale void/refund, stock adjustment, stock take, backup trigger
- tenant and branch scope checks through `require_organization_access`

Frontend route guards improve UX but do not replace backend authorization.

## Background Scheduler

The backend starts APScheduler in the FastAPI lifespan hook unless disabled.

Scheduled jobs include:

- expiry checks
- low stock checks
- near-expiry checks
- dead stock checks
- overstock checks
- cloud sync uploads when `CLOUD_SYNC_ENABLED=true`
- weekly AI manager report generation when enabled
- weekly AI report delivery retry when enabled

The scheduler uses the configured timezone, currently defaulting to `Africa/Accra`.

## Business Logic Placement

Business logic should remain in services or endpoint-local transaction blocks, not frontend code.

Current examples:

- `InventoryService`: sellable batches, stock recalculation, inventory movement records.
- `SyncOutboxService`: durable local event creation.
- `SyncUploadService`: cloud upload worker.
- `CloudProjectionService`: cloud read-model projection.
- `CloudReconciliationService`: cloud data quality checks and controlled repairs.
- `AIManagerService`: read-only assistant data collection and response composition.
- `AIWeeklyReportService`: weekly report generation.
- `AIReportDeliveryService`: email and Telegram delivery attempts.
- `AuditService`: activity log writes.
