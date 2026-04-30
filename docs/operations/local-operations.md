# Local Operations

## Installation Model

The local pharmacy installation requires:

- PostgreSQL
- backend virtual environment
- configured backend `.env`
- built frontend
- backup scripts
- operator/admin provisioning

Existing runbooks:

- `docs/WINDOWS_LOCAL_DEPLOYMENT_RUNBOOK.md`
- `docs/OFFLINE_INSTALLATION.md`
- `docs/POSTGRES_LOCAL_SETUP.md`
- `docs/CLIENT_INSTALLATION_PLAN.md`

## Daily Operator Expectations

Operators should:

- log in with assigned account
- use POS for sales
- monitor low-stock and expiry alerts
- complete stock receiving and adjustments with correct reason
- avoid sharing accounts
- report sync or backup warnings

## Manager Expectations

Managers should:

- review sales and stock summaries
- review cloud dashboard if enabled
- review reconciliation issues
- review weekly AI reports
- ensure backups are recent
- investigate failed sync or projection issues
- approve sensitive stock workflows

## Installer Expectations

Installers/support should:

- confirm PostgreSQL is running
- apply Alembic migrations
- provision admin
- verify backend health
- verify frontend connects to backend
- verify backup scripts
- run a test backup and restore drill where practical
- record the restore drill result in Settings
- confirm diagnostics page is clean

## Database Schema Operations

Production and client databases must be created as empty PostgreSQL databases, then upgraded with Alembic. Do not create or repair the application schema by copying table queries into a database editor. Manual schema replay can leave the tables, enum types, and `alembic_version` history out of sync with the backend models.

For a Docker-backed or local PostgreSQL database:

```bash
cd /home/grejoy/Projects/pharma-pos-ai/backend
venv/bin/python -m alembic upgrade head
venv/bin/python -m alembic current
```

The current revision should show the migration head. If login fails with a missing column such as `users.permissions`, the database is behind the application code and migrations must be applied before testing the frontend again.

Only the initial database and database user should be created manually, for example `CREATE DATABASE pharma_pos OWNER pharma_user;`. The application tables, indexes, constraints, enum types, and audit/sync/reporting tables belong to Alembic.
