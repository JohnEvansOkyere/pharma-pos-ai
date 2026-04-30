# Runtime And Deployment Topology

## Local Pharmacy Installation

Minimum runtime components:

- local PostgreSQL database
- FastAPI backend process
- built React frontend served locally or through a web server
- browser on the pharmacy workstation
- backup scripts and scheduled backup task

The frontend is not true offline browser storage. It requires a reachable backend. The intended offline behavior is local network/local machine availability, not cloud-free browser persistence.

## Cloud Reporting Installation

Cloud-side components:

- cloud backend or ingestion API
- Supabase Postgres
- projection worker or backend-triggered projection endpoint
- cloud dashboard routes
- AI manager services
- email/Telegram delivery integrations

The cloud layer can be unavailable without stopping local branch POS operation. Reports become stale until upload resumes.

## Environment Files

Backend environment values live under `backend/.env`.

Frontend environment values live under `frontend/.env.local` or deployment-specific frontend env configuration.

Do not mix cloud database secrets into frontend env files. API keys for OpenAI, Anthropic/Claude, Groq, SMTP, Telegram, database URLs, and sync tokens are backend/server-side values.

## Build And Test Commands

Backend:

```bash
cd backend
venv/bin/pytest tests
venv/bin/alembic heads
venv/bin/alembic upgrade head
```

Frontend:

```bash
cd frontend
npm run test
npm run build
```

## Operational Startup

Typical local startup:

1. PostgreSQL is running.
2. Backend environment is configured.
3. Alembic migrations are applied.
4. Backend starts and scheduler starts if enabled.
5. Frontend connects to local backend.
6. Operator logs in.
7. Settings/diagnostics confirms database, scheduler, backup, and sync state.

## Scheduler Jobs

Local scheduler jobs:

- expiry alerts
- low-stock alerts
- near-expiry checks
- dead-stock checks
- overstock checks
- sync upload when cloud sync is enabled
- weekly AI reports when enabled
- delivery retry for failed AI report delivery records

## Production Readiness Rule

Before any client rollout, validate:

- migrations apply cleanly
- no demo credentials are shipped
- local backup and restore have been tested
- restore drill result is recorded in Settings
- POS sale and sale reversal paths are tested
- stock adjustment and stock take paths are tested
- audit log visibility works
- sync can be disabled without breaking local POS
- cloud secrets are not committed
