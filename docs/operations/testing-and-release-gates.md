# Testing And Release Gates

## Operational Profile Isolation

Backend tests must not inherit `APP_MODE` or `POS_DEPLOYMENT_PROFILE` from a
developer's `.env`. `backend/tests/conftest.py` pins every test process to
`APP_MODE=operational_pos` and selects its deployment behavior only from
`TEST_POS_DEPLOYMENT_PROFILE`.

Run both complete suites:

```bash
cd backend
TEST_POS_DEPLOYMENT_PROFILE=offline python3 -m pytest -q
TEST_POS_DEPLOYMENT_PROFILE=hosted python3 -m pytest -q
```

The hosted profile creates a real organization and two branches. Shared user,
product, and batch fixtures receive the same organization/branch ownership, so
hosted tests exercise tenant guards instead of bypassing them.

The offline profile leaves shared fixtures unscoped. Offline installations use
their dedicated local database as the isolation boundary, so query helpers do
not introduce branch filtering merely because legacy rows or users contain
organization metadata.

## CI Gate

`.github/workflows/build.yml` runs the backend suite against PostgreSQL with a
matrix of `offline` and `hosted`. Image publication depends on both matrix jobs
and the frontend job succeeding.

Any operational change is incomplete if only one deployment profile passes.

## Migration Gate

Global identifier backfills use set-based PostgreSQL updates through
`uuid_generate_v5`. The migration enables the standard `uuid-ossp` extension
and updates organizations, branches, devices, and ingested events without
issuing one update per row. A regression test asserts that the PostgreSQL path
contains only set-based statements.
