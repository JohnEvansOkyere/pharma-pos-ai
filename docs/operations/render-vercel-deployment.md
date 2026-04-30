# Render And Vercel Deployment

## Purpose

This runbook prepares the cloud side of the hybrid deployment:

- Render runs the cloud FastAPI backend.
- Supabase Postgres stores the cloud database.
- Vercel serves the browser frontend.
- Local pharmacy installs keep their own local PostgreSQL source of truth and upload events to the Render backend.

## Backend On Render

Use the root `render.yaml` blueprint or create a Render web service manually.

Manual Render settings:

- Root directory: `backend`
- Build command: `pip install --upgrade pip && pip install -r requirements.txt`
- Start command: `bash scripts/render_start.sh`
- Health check path: `/health`

The start script runs:

```bash
python -m alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
```

This means the Supabase schema is migrated before the cloud API starts.

Required Render environment variables:

```env
DATABASE_BACKEND=postgresql
DATABASE_URL=postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres
SECRET_KEY=<generated-secret>
ENVIRONMENT=production
DEBUG=false
TIMEZONE=Africa/Accra
BACKEND_CORS_ORIGINS=["https://your-vercel-app.vercel.app","http://localhost:3000","http://localhost:5173"]
CLOUD_SYNC_REQUIRE_TOKEN=true
CLOUD_SYNC_API_TOKEN=<shared-branch-sync-token>
CLOUD_PROJECTION_ENABLED=true
CLOUD_PROJECTION_INTERVAL_MINUTES=5
CLOUD_PROJECTION_BATCH_SIZE=100
```

Optional Render variables:

```env
AI_MANAGER_PROVIDER=deterministic
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GROQ_API_KEY=
AI_WEEKLY_REPORTS_ENABLED=false
AI_WEEKLY_REPORT_DELIVERY_ENABLED=false
SMTP_HOST=
TELEGRAM_BOT_TOKEN=
```

Keep Supabase database URLs, AI keys, SMTP passwords, Telegram bot tokens, and sync tokens out of Vercel.

## Frontend On Vercel

Recommended Vercel project settings:

- Root directory: `frontend`
- Framework preset: Vite
- Build command: `npm run build`
- Output directory: `dist`

Required Vercel environment variable:

```env
VITE_API_URL=https://your-render-backend.onrender.com/api
```

Only `VITE_*` values are exposed to the browser. Do not put backend secrets in Vercel.

The frontend includes `frontend/vercel.json` so client-side routes such as `/cloud-dashboard` and `/settings` load correctly on page refresh.

## Local Branch Sync To Render

On each local pharmacy backend, keep the operational database local:

```env
DATABASE_URL=
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=pharma_pos
POSTGRES_USER=pharma_user
POSTGRES_PASSWORD=<local-password>
```

Then configure sync to the Render backend:

```env
CLOUD_SYNC_ENABLED=true
CLOUD_SYNC_INGEST_URL=https://your-render-backend.onrender.com/api/sync/ingest
CLOUD_SYNC_API_TOKEN=<same-token-configured-on-render>
CLOUD_SYNC_DEVICE_UID=<registered-device-uid>
CLOUD_SYNC_ORGANIZATION_ID=<organization-id>
CLOUD_SYNC_BRANCH_ID=<branch-id>
```

## Required Cloud Provisioning

Before sync will work:

- create the organization row
- create the branch row
- create the active device row with the same `CLOUD_SYNC_DEVICE_UID`
- assign cloud dashboard users to the correct `organization_id` and optional `branch_id`

The ingest endpoint rejects unregistered, disabled, or wrong-tenant devices.

## Operational Notes

- Alembic creates the Supabase schema; sync does not create tables.
- Local branch data remains the operational source of truth.
- Render receives events and writes cloud reporting/read-model tables.
- `CLOUD_PROJECTION_ENABLED=true` on Render projects accepted events into dashboard and AI reporting tables.
- If Render is down, local POS continues and the local outbox retries later.
