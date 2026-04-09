# Comprehensive Technical Audit

## Scope

Audit target: the full `pharma-pos-ai` repository, with emphasis on regulated pharmacy workflows, offline/local deployment readiness, security, auditability, data integrity, and operator safety.

Verification performed:
- source review across backend models, APIs, services, schemas, migrations, deployment scripts, frontend pages/stores, and documentation
- static compilation check: `backend/venv/bin/python -m compileall backend/app scripts`
- frontend production build: `npm run build`
- backend test discovery: `venv/bin/pytest` returned no collected tests

Re-verification note:
- the claims in this report are backed by source code and runtime artifacts, not just documentation
- documentation was used only to cross-check release-facing wording and packaging claims
- after re-checking the source, there is no public `/register` endpoint in the current backend codebase

## Executive Summary

This codebase is still closer to a structured prototype than a deployable pharmacy product.

The most important blockers are:
- committed secrets, demo credentials, and runtime artifacts in the repository
- a broken batch-update backend path that will fail at runtime
- missing server-side enforcement for pharmacy-specific dispensing rules
- no automated tests
- misleading offline/production claims in UI and docs

The project has a usable architecture skeleton, but the current implementation does not yet provide the correctness, traceability, and recoverability expected for a pharmacy installation.

## Rating

- Overall readiness: **High Risk**
- Compliance readiness score: **3/10**

Justification:
- the core data model includes pharmacy concepts, but the enforcement layer is incomplete
- the sale, batch, and audit paths are not yet reliable enough for regulated dispensing
- offline/local deployment is mostly packaging and wording, not durable offline behavior
- no regression test suite is present to protect core transactional flows

## 1. Architecture & Design

### Summary

The codebase is organized into sensible FastAPI and React layers, but the actual runtime boundaries are weak. Several concerns that should live in a domain/service layer are handled directly in endpoint functions, and the repository contains multiple competing schema/deployment sources of truth.

### Critical Issues

- A critical batch-maintenance endpoint is broken by undefined variables, which indicates the API layer is carrying too much ad hoc workflow logic.
- The repository has divergent schema/deployment definitions in SQL, Alembic, ORM models, and seed scripts, which will create drift during installation and maintenance.

### Major Issues

- Endpoint modules contain large amounts of business logic instead of delegating to a transaction/service layer.
- The frontend app shell claims offline readiness, but the actual architecture is still tightly coupled to live API availability.
- The backend app startup does not guard against misconfiguration beyond the settings module, so deployment failures can surface late.

### Minor Issues / Recommendations

- Introduce a dedicated domain/service layer for sales, stock movement, and compliance validation.
- Consolidate schema ownership around ORM models plus migrations, and treat raw SQL as install-time support only.
- Split dashboard/reporting code away from POS-critical paths for faster startup and smaller operator-facing bundles.

### Code References

- [backend/app/api/endpoints/products.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/products.py#L527)
- [backend/app/api/endpoints/sales.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/sales.py#L72)
- [database/init.sql](/home/grejoy/Projects/pharma-pos-ai/database/init.sql#L240)
- [backend/app/main.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/main.py#L1)
- [frontend/src/pages/DashboardPage.tsx](/home/grejoy/Projects/pharma-pos-ai/frontend/src/pages/DashboardPage.tsx#L1)

## 2. Code Quality & Maintainability

### Summary

The code is readable, but maintainability is weakened by duplicated logic, oversized endpoint functions, and a missing test suite. Several files also show signs of partial refactors or dead paths.

### Critical Issues

- There are no backend tests in `backend/tests`, so the project has no regression net for auth, sales, stock, or compliance rules.

### Major Issues

- `backend/app/api/endpoints/products.py` contains many helper functions plus multi-step transaction workflows, making it difficult to reason about and easy to break.
- `frontend/src/pages/ProductsPage.tsx` is a very large component with product CRUD, receiving, pricing, batch management, and pagination all mixed together.
- `frontend/src/services/api.ts` contains indentation and consistency issues, which is a sign that client-side API handling needs cleanup.

### Minor Issues / Recommendations

- Normalize naming and trim unused code paths left over from prototype iterations.
- Add tests before refactoring critical code so behavior stays stable.
- Use smaller components for modals, tables, and workflow panels in the frontend.

### Code References

- [backend/tests](/home/grejoy/Projects/pharma-pos-ai/backend/tests)
- [backend/app/api/endpoints/products.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/products.py#L1)
- [frontend/src/pages/ProductsPage.tsx](/home/grejoy/Projects/pharma-pos-ai/frontend/src/pages/ProductsPage.tsx#L1)
- [frontend/src/services/api.ts](/home/grejoy/Projects/pharma-pos-ai/frontend/src/services/api.ts#L233)

## 3. Data Integrity & Pharmaceutical Compliance

### Summary

The domain model recognizes pharmacy concepts such as batches, expiry dates, prescription flags, and controlled-stock indicators, but the enforcement is incomplete. In a regulated setting, the current write paths still allow silent data corruption or missing compliance evidence.

### Critical Issues

- Sales are not fully enforced against pharmacy rules such as prescription checks, controlled-drug ID capture, or batch-level FEFO dispensing.
- Money fields are stored as floating point values in several backend models and SQL schemas, which risks rounding drift in financial and stock-related calculations.
- The batch update route is broken, so batch metadata corrections cannot be relied on operationally.

### Major Issues

- Product and sale models rely on aggregate `total_stock` and do not maintain a full immutable movement ledger.
- The `activity_logs` model exists, but the actual write paths do not populate it, so critical changes are not auditable.
- The current stock adjustment flow records a correction but does not create a defensible ledger of before/after state.

### Minor Issues / Recommendations

- Enforce `Decimal`/numeric types for prices throughout the stack and keep database columns consistent.
- Add server-side validation for `prescription_status`, `is_narcotic`, `requires_id`, `customer_id_number`, `prescription_number`, and `doctor_name`.
- Add explicit validation for batch recall, quarantine, and expiry override reasons.

### Code References

- [backend/app/models/product.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/models/product.py#L1)
- [backend/app/models/sale.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/models/sale.py#L1)
- [backend/app/models/stock_adjustment.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/models/stock_adjustment.py#L1)
- [backend/app/models/activity_log.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/models/activity_log.py#L1)
- [backend/app/api/endpoints/sales.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/sales.py#L72)
- [backend/app/api/endpoints/stock_adjustments.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/stock_adjustments.py#L74)
- [backend/app/api/endpoints/products.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/products.py#L457)
- [database/init.sql](/home/grejoy/Projects/pharma-pos-ai/database/init.sql#L186)

## 4. Security

### Summary

The security posture is not release-safe. The repository contains live secrets and demo credentials, and the UI still exposes development-only login guidance. Authentication/authorization exists, but secret management and release hygiene are weak.

### Critical Issues

- `backend/.env` contains a committed database password and JWT secret.
- `frontend/src/pages/LoginPage.tsx` displays demo credentials directly in the release UI.
- `README.md`, `installer.iss`, and `docs/root-docs/INSTALLATION_SUCCESS.txt` still describe default admin credentials, which is dangerous for a customer-facing build.

### Major Issues

- `backend/app/core/config.py` generates a random secret at runtime when not configured, which is unacceptable for production stability.
- `backend/alembic.ini` contains a hardcoded database URL with the same credential pattern.
- `docker-compose.yml` ships a default fallback secret and password values.
- `system_ops.py` exposes backup execution through a manager-only endpoint that shells out to platform scripts, so the blast radius depends entirely on the local environment and script integrity.

### Minor Issues / Recommendations

- Add secret scanning and pre-commit rules for `.env`, `.db`, `.backup`, and seed artifacts.
- Treat all installer-generated credentials as first-run only, never as persisted defaults.
- Review file-system and subprocess permissions for the backup/restore utilities on Windows and Linux.

### Code References

- [backend/.env](/home/grejoy/Projects/pharma-pos-ai/backend/.env)
- [backend/app/core/config.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/core/config.py#L1)
- [backend/alembic.ini](/home/grejoy/Projects/pharma-pos-ai/backend/alembic.ini#L60)
- [docker-compose.yml](/home/grejoy/Projects/pharma-pos-ai/docker-compose.yml#L1)
- [frontend/src/pages/LoginPage.tsx](/home/grejoy/Projects/pharma-pos-ai/frontend/src/pages/LoginPage.tsx#L1)
- [README.md](/home/grejoy/Projects/pharma-pos-ai/README.md#L175)
- [installer.iss](/home/grejoy/Projects/pharma-pos-ai/installer.iss#L1)
- [backend/app/api/endpoints/system_ops.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/system_ops.py#L87)

## 5. Offline System Reliability

### Summary

The product is local-first in topology, but not truly offline-first in behavior. It requires a live backend for almost all workflows, and the current backup/recovery story is more diagnostic than operationally robust.

### Critical Issues

- The frontend cannot continue pharmacy operations without a live backend because it has no durable offline queue or local data store.
- The app marketability claims around offline behavior are stronger than the implementation.

### Major Issues

- The PWA cache configuration does not match the actual `/api` path used by the client.
- The backend local database path is not hard-hardened for concurrency, recovery, or corruption handling in a pharmacy workstation scenario.
- Backup/restore scripts exist, but there is no evidence of tested restore validation or repair tooling.

### Minor Issues / Recommendations

- Make the offline model explicit: local backend required at all times, or true offline-first storage/sync.
- Document restore drill procedures and test them on a fresh machine.
- Add a startup health gate that validates database connectivity, migrations, and backup readiness before exposing the app.

### Code References

- [frontend/vite.config.ts](/home/grejoy/Projects/pharma-pos-ai/frontend/vite.config.ts#L1)
- [frontend/src/services/api.ts](/home/grejoy/Projects/pharma-pos-ai/frontend/src/services/api.ts#L1)
- [frontend/src/stores/authStore.ts](/home/grejoy/Projects/pharma-pos-ai/frontend/src/stores/authStore.ts#L1)
- [backend/app/db/base.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/db/base.py#L1)
- [backend/app/api/endpoints/system_ops.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/system_ops.py#L40)
- [scripts/backup_postgres.sh](/home/grejoy/Projects/pharma-pos-ai/scripts/backup_postgres.sh#L1)
- [scripts/restore_postgres.sh](/home/grejoy/Projects/pharma-pos-ai/scripts/restore_postgres.sh#L1)

## 6. Performance

### Summary

The system will likely work at small scale, but several implementation choices will degrade as data volume grows. The biggest performance concern is not raw algorithmic complexity but repeated full-table or repeated-per-row work in dashboard and product flows.

### Critical Issues

- The dashboard and reporting endpoints repeatedly load ORM objects and nested relations in Python loops, which will not scale well.

### Major Issues

- `dashboard.py` performs repeated per-sale and per-item product lookups instead of using aggregate queries or joined projections.
- Product list/catalog code recalculates nearest expiry and category names in ways that can become expensive on larger inventories.
- The frontend bundle is large enough to trigger a chunk size warning during build.

### Minor Issues / Recommendations

- Add targeted indexes and rewrite expensive reporting endpoints to use fewer ORM round-trips.
- Split dashboard code by widget and defer non-critical reporting until after POS-critical screens load.
- Use pagination and server-side filtering consistently for product and sales views.

### Code References

- [backend/app/api/endpoints/dashboard.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/dashboard.py#L19)
- [backend/app/api/endpoints/products.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/products.py#L128)
- [frontend/src/pages/DashboardPage.tsx](/home/grejoy/Projects/pharma-pos-ai/frontend/src/pages/DashboardPage.tsx#L1)
- [frontend/src/pages/ProductsPage.tsx](/home/grejoy/Projects/pharma-pos-ai/frontend/src/pages/ProductsPage.tsx#L1)

## 7. Dependency & Supply Chain Health

### Summary

The project uses a sensible mainstream stack, but dependency governance is weak. Some pinned versions are old, the frontend bundle warns about outdated baseline data, and there is no evidence of automated vulnerability or license scanning.

### Critical Issues

- `backend/requirements.txt` and `frontend/package.json` pin many versions without visible scanning, lockfile policy, or upgrade cadence.

### Major Issues

- The frontend build reports an outdated `baseline-browser-mapping` dataset.
- There is no dependency audit output in the repository, and no SBOM or vulnerability check is documented.

### Minor Issues / Recommendations

- Add dependency audit automation for both npm and Python.
- Remove unused packages before release packaging.
- Track licenses and CVEs for workstation deployment review.

### Code References

- [backend/requirements.txt](/home/grejoy/Projects/pharma-pos-ai/backend/requirements.txt#L1)
- [frontend/package.json](/home/grejoy/Projects/pharma-pos-ai/frontend/package.json#L1)
- [frontend/vite.config.ts](/home/grejoy/Projects/pharma-pos-ai/frontend/vite.config.ts#L1)

## 8. Regulatory & Audit Readiness

### Summary

This is the area with the largest gap. The data model suggests auditability, but the actual implementation does not yet produce a tamper-evident or inspection-ready audit trail. Several release-facing claims also overstate actual capability.

### Critical Issues

- The `ActivityLog` table exists, but no critical write path populates it, so changes to stock, sales, and users are not traceable.
- The UI still says `Offline Ready` and `Offline-capable` even though the app is not truly offline-first.
- Demo credentials remain visible in the login page and installation materials.

### Major Issues

- There is no batch-level dispense audit linked to actual stock depletion.
- There is no explicit override workflow for controlled-drug, prescription-only, or quarantined-stock events.
- There is no evidence of recall or expiry-block enforcement beyond display and alerting.

### Minor Issues / Recommendations

- Add immutable audit events for create/update/delete, sale completion, stock receipt, stock adjustment, and user management.
- Add operator identity, reason codes, and before/after values to every sensitive mutation.
- Remove unsupported product claims from release docs and UI labels.

### Code References

- [backend/app/models/activity_log.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/models/activity_log.py#L1)
- [backend/app/models/product.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/models/product.py#L1)
- [backend/app/models/sale.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/models/sale.py#L1)
- [backend/app/models/stock_adjustment.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/models/stock_adjustment.py#L1)
- [frontend/src/components/layout/Sidebar.tsx](/home/grejoy/Projects/pharma-pos-ai/frontend/src/components/layout/Sidebar.tsx#L1)
- [frontend/src/pages/LoginPage.tsx](/home/grejoy/Projects/pharma-pos-ai/frontend/src/pages/LoginPage.tsx#L1)
- [README.md](/home/grejoy/Projects/pharma-pos-ai/README.md#L1)

## 9. Cross-Cutting Findings

### Critical Issues

- Committed secrets and demo credentials are present in the repository.
- No automated tests were found.
- Batch update is broken at runtime.

### Major Issues

- Financial values use floating point storage and calculations in multiple places.
- There are multiple schema sources with mismatched semantics.
- Dashboard/reporting code is heavy and uses repeated ORM lookups.
- Offline readiness is not real yet.

### Minor Issues / Recommendations

- Introduce CI checks for linting, tests, build, dependency scanning, and secret scanning.
- Add explicit release-build configuration that removes demo data and marketing claims.

## Risk Matrix

### High

- committed secrets and demo credentials
- no automated backend tests
- broken batch update endpoint
- missing enforcement for prescription/controlled-drug dispensing
- no populated audit trail for critical writes
- misleading offline/production claims

### Medium

- float-based money fields
- repeated ORM lookups in reports/dashboard
- weak offline recovery story
- bundle size and startup overhead
- dependency governance gaps

### Low

- style inconsistencies
- incomplete cleanup of prototype-era wording
- minor UX issues such as redirect churn and bulky screens

## Prioritized Action Plan

1. Remove release-blocking secrets, demo credentials, and unsupported claims from all shipped artifacts.
2. Fix the broken batch update workflow and add regression tests for products, batches, sales, and user management.
3. Move money handling to exact numeric/decimal storage end-to-end.
4. Implement server-side pharmacy compliance rules for prescription-only and controlled-drug sales.
5. Add immutable audit logging for all critical writes.
6. Decide and implement the real offline model, then harden backup/restore and startup checks around it.
7. Refactor dashboard/reporting and split non-critical UI code away from POS-critical paths.
8. Add dependency scanning, secret scanning, and a basic release gate in CI.

## Verification Notes

- Backend source compiled successfully with `compileall`.
- Frontend production build completed successfully.
- `pytest` found zero tests, which is itself a major readiness gap.

## Final Assessment

This repository has a solid starting structure, but it is not yet appropriate for a regulated pharmacy rollout. The current implementation still needs security cleanup, transaction hardening, auditability, and test coverage before it can be treated as a safe local pharmacy product.

## Remediation Status Update

This audit was partially remediated on 2026-04-09 during the production-hardening pass for customer installs. The original findings above remain the historical audit record; the items below reflect what has now been fixed in source.

### Remediated In Source

- Committed runtime defaults were sanitized in shipped config and deployment artifacts:
  - [backend/.env](/home/grejoy/Projects/pharma-pos-ai/backend/.env#L1)
  - [backend/alembic.ini](/home/grejoy/Projects/pharma-pos-ai/backend/alembic.ini#L60)
  - [backup.bat](/home/grejoy/Projects/pharma-pos-ai/backup.bat#L1)
  - [restore.bat](/home/grejoy/Projects/pharma-pos-ai/restore.bat#L1)
  - [setup-env.bat](/home/grejoy/Projects/pharma-pos-ai/setup-env.bat#L1)
- Demo credentials and unsupported release claims were removed from the active UI and install docs:
  - [frontend/src/pages/LoginPage.tsx](/home/grejoy/Projects/pharma-pos-ai/frontend/src/pages/LoginPage.tsx#L1)
  - [frontend/src/components/layout/Sidebar.tsx](/home/grejoy/Projects/pharma-pos-ai/frontend/src/components/layout/Sidebar.tsx#L1)
  - [README.md](/home/grejoy/Projects/pharma-pos-ai/README.md#L1)
  - [docs/WINDOWS_LOCAL_DEPLOYMENT_RUNBOOK.md](/home/grejoy/Projects/pharma-pos-ai/docs/WINDOWS_LOCAL_DEPLOYMENT_RUNBOOK.md#L1)
- Customer install provisioning now requires a site-specific administrator:
  - [scripts/provision_admin.py](/home/grejoy/Projects/pharma-pos-ai/scripts/provision_admin.py#L1)
  - [provision-admin.bat](/home/grejoy/Projects/pharma-pos-ai/provision-admin.bat#L1)
  - [installer.iss](/home/grejoy/Projects/pharma-pos-ai/installer.iss#L1)
- Critical runtime product/batch defects were fixed and covered by tests:
  - [backend/app/api/endpoints/products.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/products.py#L1)
  - [backend/tests/test_inventory_workflows.py](/home/grejoy/Projects/pharma-pos-ai/backend/tests/test_inventory_workflows.py#L1)
- Audit logging was added to key write paths:
  - [backend/app/services/audit_service.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/services/audit_service.py#L1)
  - [backend/app/api/endpoints/products.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/products.py#L1)
  - [backend/app/api/endpoints/sales.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/sales.py#L1)
  - [backend/app/api/endpoints/stock_adjustments.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/stock_adjustments.py#L1)
  - [backend/app/api/endpoints/users.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/users.py#L1)
  - [backend/app/api/endpoints/categories.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/categories.py#L1)
  - [backend/app/api/endpoints/suppliers.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/suppliers.py#L1)
- Large-data query pressure was reduced in product search and dashboard/reporting paths:
  - [backend/app/api/endpoints/products.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/products.py#L1)
  - [backend/app/api/endpoints/dashboard.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/dashboard.py#L1)
- Frontend startup was improved by route-level code splitting:
  - [frontend/src/App.tsx](/home/grejoy/Projects/pharma-pos-ai/frontend/src/App.tsx#L1)

### Still Open

- Money values still use floating-point fields and calculations, which is not ideal for long-term accounting correctness:
  - [backend/app/models/product.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/models/product.py#L1)
  - [backend/app/models/sale.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/models/sale.py#L1)
- Prescription and controlled-drug enforcement remains out of scope for this hardening pass at the user's request:
  - [backend/app/api/endpoints/sales.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/sales.py#L1)
  - [backend/app/models/product.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/models/product.py#L1)
- Automated coverage exists only for critical inventory flows and should be expanded before broad rollout:
  - [backend/tests/test_inventory_workflows.py](/home/grejoy/Projects/pharma-pos-ai/backend/tests/test_inventory_workflows.py#L1)
  - [backend/tests/test_auth_and_user_workflows.py](/home/grejoy/Projects/pharma-pos-ai/backend/tests/test_auth_and_user_workflows.py#L1)
  - [backend/tests/test_sales_financial_integrity.py](/home/grejoy/Projects/pharma-pos-ai/backend/tests/test_sales_financial_integrity.py#L1)

### Additional Remediation Completed

- Monetary storage for products, batches, sales, and sale items was moved from floating point columns to fixed-scale numerics:
  - [backend/app/models/product.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/models/product.py#L1)
  - [backend/app/models/sale.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/models/sale.py#L1)
  - [backend/alembic/versions/54f6c3e7c2d1_convert_money_columns_to_numeric.py](/home/grejoy/Projects/pharma-pos-ai/backend/alembic/versions/54f6c3e7c2d1_convert_money_columns_to_numeric.py#L1)
- Money normalization and rounding are now centralized for critical write paths:
  - [backend/app/core/money.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/core/money.py#L1)
  - [backend/app/api/endpoints/products.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/products.py#L1)
  - [backend/app/api/endpoints/sales.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/sales.py#L1)
- Audit logging now serializes fixed-scale decimals safely in JSON audit payloads:
  - [backend/app/services/audit_service.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/services/audit_service.py#L1)
- User-management coverage and behavior were tightened, including username updates and role restrictions:
  - [backend/app/api/endpoints/users.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints/users.py#L1)
  - [backend/tests/test_auth_and_user_workflows.py](/home/grejoy/Projects/pharma-pos-ai/backend/tests/test_auth_and_user_workflows.py#L1)

### Re-Verification After Remediation

- `venv/bin/python -m compileall app` in [backend](/home/grejoy/Projects/pharma-pos-ai/backend)
- `venv/bin/pytest` in [backend](/home/grejoy/Projects/pharma-pos-ai/backend): 8 passed
- `npm run build` in [frontend](/home/grejoy/Projects/pharma-pos-ai/frontend): passed
