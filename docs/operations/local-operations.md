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
- confirm diagnostics page is clean
