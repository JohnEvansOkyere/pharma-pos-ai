# Phase 10 Implementation Verification

**Date:** 2026-06-07
**Auditor:** Codex
**Scope:** Independent verification of Claude's review of commits `38138e0` through `cea403f`.

## Verdict

Claude's release-blocking conclusion is correct: the hosted operational profile is not
verified by a green system-level regression suite and must not be treated as deployable.
The architecture and focused tests are useful foundation work, but hosted release
acceptance is incomplete.

One statement was too absolute: there is a passing configuration. With
`APP_MODE=operational_pos POS_DEPLOYMENT_PROFILE=auto`, the full backend suite passes
`201 passed, 1 warning`. That is the offline/default path. It does not prove hosted
behavior.

## Reproduced Results

- Repository `backend/.env` (`APP_MODE=online_pos`): `20 failed, 181 passed`.
- Explicit hosted profile: `21 failed, 180 passed`.
- Explicit offline profile: `1 failed, 200 passed`; the remaining settings test inherits
  the forced profile and demonstrates environment-sensitive tests.
- Default/CI-style auto profile: `201 passed, 1 warning`.
- The checked-in `backend/venv` currently cannot collect the suite because `boto3` is
  absent, although it is pinned in `backend/requirements.txt`. The system Python used
  for the results above has the pinned dependency installed.

## Confirmed Findings

1. Shared `admin_user`, `manager_user`, and `cashier_user` fixtures have no organization
   or branch. Hosted operational routes correctly reject them, causing broad failures
   across sales, products, dashboard, stock adjustments, stock takes, and user workflows.
2. Tests consume process/environment settings. CI runs one unpinned default profile, so
   it verifies offline/default behavior but never runs a hosted profile.
3. `scope_query_to_user()` applies organization and branch filters whenever those fields
   exist on the user, including offline deployments. That semantic change needs an
   explicit product decision and regression coverage.
4. Migration `q2r3s4t5u6v7` performs row-by-row Python backfills for organizations,
   branches, devices, and ingested sync events. The central-event loop is the highest
   growth risk and should be replaced with set-based PostgreSQL updates before scale.

## Required Remediation

1. Add profile-isolated fixtures and tenant-scoped hosted users/data.
2. Run the backend suite in both offline and hosted CI matrix entries.
3. Decide and test offline branch-scoping semantics.
4. Convert migration backfills to set-based SQL and test migration upgrade behavior.

## Remediation Verification

**Implemented:** 2026-06-07 13:18 UTC

- Shared hosted users, products, and batches now use one real organization and
  branch context. Deliberate cross-branch tests still create separate records.
- `TEST_POS_DEPLOYMENT_PROFILE` is the only test deployment selector; an
  autouse fixture pins global runtime settings and prevents `.env` leakage.
- Offline query scoping explicitly preserves whole-database visibility because
  the dedicated local database is the offline isolation boundary. Hosted
  queries retain organization and branch enforcement.
- GitHub Actions now has PostgreSQL `offline` and `hosted` matrix entries.
- Customer-retention tests now create real organizations and sale users,
  removing foreign-key assumptions that SQLite previously concealed.
- PostgreSQL UUIDv5 backfills are set-based through `uuid-ossp`. A fresh
  database drill from `p1q2r3s4t5u6` to `q2r3s4t5u6v7` verified all generated
  identifiers against their UUIDv5 formulas.
- Repository virtualenv dependencies were synchronized with
  `backend/requirements.txt`.

Verification results:

- PostgreSQL offline profile: `204 passed, 1 warning`.
- PostgreSQL hosted profile: `204 passed, 1 warning`.
- SQLite fallback offline profile: `204 passed, 1 warning`.
- SQLite fallback hosted profile: `204 passed, 1 warning`.
- Frontend: `22 passed`; `npx tsc --noEmit` passed.
- GitHub workflow YAML parsed successfully.

The code-side remediation is complete. Final checklist acceptance remains
pending until the pushed GitHub Actions matrix reports green.
