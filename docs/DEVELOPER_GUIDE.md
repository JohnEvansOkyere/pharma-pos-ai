# Developer Guide

## Purpose

This guide is for developers working on Pharma POS AI.

The current product target is:
- local-first pharmacy installation
- PostgreSQL on the client machine
- local backend required for operation
- frontend used by pharmacy staff on the same machine or local network

This is not yet a true offline-sync product.

## Core Principles

- protect data integrity first
- keep stock workflows batch-aware
- treat POS as the highest-priority workflow
- avoid making claims the software does not actually support
- optimize for reliability and supportability over novelty

## Current Architecture

### Backend

- FastAPI application in [backend/app](/home/grejoy/Projects/pharma-pos-ai/backend/app)
- SQLAlchemy models in [backend/app/models](/home/grejoy/Projects/pharma-pos-ai/backend/app/models)
- API endpoints in [backend/app/api/endpoints](/home/grejoy/Projects/pharma-pos-ai/backend/app/api/endpoints)
- scheduler in [backend/app/services/scheduler.py](/home/grejoy/Projects/pharma-pos-ai/backend/app/services/scheduler.py)

### Frontend

- React + TypeScript application in [frontend/src](/home/grejoy/Projects/pharma-pos-ai/frontend/src)
- page-level workflows in [frontend/src/pages](/home/grejoy/Projects/pharma-pos-ai/frontend/src/pages)
- layout shell in [frontend/src/components/layout](/home/grejoy/Projects/pharma-pos-ai/frontend/src/components/layout)
- API client in [frontend/src/services/api.ts](/home/grejoy/Projects/pharma-pos-ai/frontend/src/services/api.ts)

### Database

- local PostgreSQL is the intended deployment database
- Alembic migrations live in [backend/alembic](/home/grejoy/Projects/pharma-pos-ai/backend/alembic)
- setup notes live in [POSTGRES_LOCAL_SETUP.md](/home/grejoy/Projects/pharma-pos-ai/docs/POSTGRES_LOCAL_SETUP.md)

## Local Development Setup

### Backend

```bash
cd /home/grejoy/Projects/pharma-pos-ai/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Database

Configure PostgreSQL in:

- [backend/.env](/home/grejoy/Projects/pharma-pos-ai/backend/.env)

Initialize schema from repo root:

```bash
cd /home/grejoy/Projects/pharma-pos-ai
bash scripts/init_db.sh
```

Optional development seed:

```bash
SEED_DATABASE=true bash scripts/init_db.sh
```

### Run Backend

```bash
cd /home/grejoy/Projects/pharma-pos-ai/backend
uvicorn app.main:app --reload
```

### Run Frontend

```bash
cd /home/grejoy/Projects/pharma-pos-ai/frontend
npm install
npm run dev
```

## Critical Workflows

These workflows should be treated as release-critical:

- login and role loading
- product creation and product edit
- stock receipt
- batch management and quarantine
- POS sale creation
- stock depletion and sellable stock calculation
- backup and restore

Any change touching these areas should be verified before merge.

## Product Workflow Expectations

### Products

- product master data should be editable separately from stock receipt
- opening stock should be optional during product creation
- batches must carry batch number, quantity, expiry, and cost

### Inventory

- sellable stock should exclude quarantined batches
- FEFO should remain the default stock depletion rule
- stock corrections should be traceable

### POS

- cashier should land in POS, not dashboard
- product search should stay fast with large catalogs
- totals must remain visible during sale building

## Backend Guardrails

Current backend validations include:

- duplicate SKU and barcode protection
- batch date validation
- pricing sanity checks for product creation and stock receipt
- inactive user blocking

Still needed for stronger production readiness:

- broader audit logging on critical writes
- more regression coverage
- recovery and health tooling

## Frontend Guardrails

- do not hide critical totals behind page scroll
- do not make pharmacy operators navigate through admin-only routes
- prefer explicit, dense operational layouts over decorative dashboards

## Verification Checklist For Code Changes

Use the smallest meaningful verification for the files you touched.

Typical checks:

```bash
python -m py_compile backend/app/api/endpoints/products.py
python -m py_compile backend/app/api/endpoints/auth.py
cd /home/grejoy/Projects/pharma-pos-ai/frontend && npm run build
```

If you touched auth, stock, products, or POS, verify the exact flow manually as well.

## Release Discipline

Before a release-facing build:

- remove demo credentials from release-facing screens
- do not ship `.env`, `.db`, or backup artifacts
- verify backups and restore
- review [Go-Live Checklist](/home/grejoy/Projects/pharma-pos-ai/docs/GO_LIVE_CHECKLIST.md)

## Documentation Map

Use these documents alongside this guide:

- [Client User Guide](/home/grejoy/Projects/pharma-pos-ai/docs/CLIENT_USER_GUIDE.md)
- [Windows Local Deployment Runbook](/home/grejoy/Projects/pharma-pos-ai/docs/WINDOWS_LOCAL_DEPLOYMENT_RUNBOOK.md)
- [Backup And Restore Guide](/home/grejoy/Projects/pharma-pos-ai/docs/BACKUP_RESTORE_GUIDE.md)
- [Go-Live Checklist](/home/grejoy/Projects/pharma-pos-ai/docs/GO_LIVE_CHECKLIST.md)
