# Add / Remove Recommendations For Real Pharmacy Rollout

## Objective

Changes recommended before packaging this product for real pharmacies, especially where the installation must run offline on-site.

## Add

### 1. Add first-run provisioning

- installer-generated admin account
- forced password reset on first login
- persisted `SECRET_KEY`
- machine-specific configuration wizard

### 2. Add true pharmacy inventory controls

- batch-aware sales depletion
- FEFO dispensing
- stock receiving workflow
- stock adjustment approval flow
- returns, voids, and refunds with audit reasons
- recalled/expired/quarantined stock blocking

### 3. Add prescription and compliance enforcement

- required prescription capture for prescription-only items
- ID capture and override controls for controlled substances
- pharmacist approval workflow where applicable
- immutable dispensing audit trail

### 4. Add offline operations support

- clear architecture decision: local backend appliance or real offline-first sync client
- automated local backups
- restore and backup verification tools
- data export for migration/support
- local health dashboard for operators

### 5. Add observability and supportability

- structured logs
- error reporting for install/support mode
- database integrity checks
- repair/maintenance scripts
- admin diagnostics screen

### 6. Add testing and release controls

- backend unit and integration tests
- frontend workflow tests
- end-to-end tests for login, sale, stock receipt, and reports
- release checklist for offline install validation

### 7. Add hardware and pharmacy workflow integrations

- receipt printer support
- barcode scanner validation
- optional label printing
- cash drawer support if relevant
- report exports designed for local operations

## Remove

### 1. Remove public self-registration from production

Reason:
- it is a critical security flaw

### 2. Remove demo credentials and sample bootstrap users from production packaging

Reason:
- unacceptable for a commercial pharmacy release

### 3. Remove committed runtime artifacts from shipped builds

Items to exclude:
- `.env`
- `backend/.env`
- `frontend/.env.local`
- `*.db`
- `*.backup`

Reason:
- these create data leakage and deployment hygiene risks

### 4. Remove or relabel unsupported marketing claims

Examples:
- "Offline Ready"
- "Offline-capable"
- "AI insights" if the feature is rule-based and not materially intelligent

Reason:
- product language should match actual behavior

### 5. Remove incomplete UI controls from release builds

Examples:
- inert supplier actions
- unfinished analytics widgets
- any page that depends on mocked values

Reason:
- incomplete controls reduce operator trust

### 6. Remove dev-only operational components from production default installs

Examples:
- pgAdmin in standard deployment bundles
- development-only seeding paths
- dev-facing API docs if the install is customer-facing

Reason:
- reduces attack surface and support complexity

## Replace

### 1. Replace count-based invoice numbering

With:
- database-backed sequence or durable serial strategy

### 2. Replace aggregate-only stock deduction

With:
- batch-level stock movement ledger

### 3. Replace runtime-generated secret fallback

With:
- installation-time secret generation stored durably

### 4. Replace mock dashboard metrics

With:
- real metrics or no metric

## Suggested Priority Order

### Phase 1: Blockers

- remove public registration
- fix local database reliability
- remove demo credentials from release path
- implement batch-safe sales logic
- enforce prescription rules

### Phase 2: Deployment Readiness

- add installer-first provisioning
- add backups and restore tools
- add audit logs
- add automated tests

### Phase 3: Product Maturity

- complete offline architecture
- add hardware integration polish
- improve analytics and reporting fidelity

## Commercial Positioning Recommendation

Until the blocker items are fixed, position this as:

- a custom internal pharmacy management prototype, not
- a production-ready commercial pharmacy POS

That distinction matters. Real pharmacies will evaluate this primarily on correctness, traceability, continuity of operation, and supportability, not on interface polish alone.
