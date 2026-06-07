# Docker Environment Profiles

The source-built Docker setup keeps backend and frontend profiles in their own
application directories:

| Backend profile | Frontend profile | Runtime mode | Deployment | Database |
| --- | --- | --- | --- |
| `backend/.env_local` | `frontend/.env_local` | `operational_pos` | `offline` | Local Docker PostgreSQL |
| `backend/.env_cloud` | `frontend/.env_cloud` | `operational_pos` | `hosted` | Dedicated Render Postgres |

`cloud_reporting` remains a separate mode for the central vendor portal because
it rejects pharmacy operational writes.

## First-Time Setup

Create private working copies of the committed templates:

```bash
cp backend/.env_local.example backend/.env_local
cp backend/.env_cloud.example backend/.env_cloud
cp frontend/.env_local.example frontend/.env_local
cp frontend/.env_cloud.example frontend/.env_cloud
```

Edit the backend profiles and replace every placeholder credential. The
frontend profiles contain browser-safe values only. Never commit private
environment files.

For `backend/.env_cloud`, the important values are:

```env
APP_MODE=operational_pos
POS_DEPLOYMENT_PROFILE=hosted
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
SECRET_KEY=<the tenant backend JWT secret>
CLOUD_SYNC_ENABLED=true
CLOUD_SYNC_INGEST_URL=https://your-central-backend.onrender.com/api/sync/ingest
CLOUD_SYNC_API_TOKEN=<tenant-publish-token>
```

The matching `frontend/.env_cloud` contains:

```env
VITE_API_URL=/api
VITE_APP_MODE=operational_pos
VITE_POS_DEPLOYMENT_PROFILE=hosted
VITE_CUSTOMER_RETENTION_ENABLED=true
VITE_OFFLINE_QUEUE_ENABLED=true
```

## Select Local/Village Mode

```bash
cp backend/.env_local backend/.env
cp frontend/.env_local frontend/.env.local
docker compose --env-file frontend/.env.local up -d --build
```

The backend uses the local `db` service and the operational frontend is built
with the offline deployment profile.

## Select Cloud/City Mode

```bash
cp backend/.env_cloud backend/.env
cp frontend/.env_cloud frontend/.env.local
docker compose --env-file frontend/.env.local up -d --build
```

For development, the backend can run in local Docker while connecting through
`DATABASE_URL` to the hosted tenant database. Production uses a dedicated
Render backend plus Render Postgres for each pharmacy. The frontend is rebuilt
with the hosted feature flags.

The compose file currently starts the local PostgreSQL container in both
profiles. In cloud mode that container is unused; `DATABASE_URL` controls the
backend's real database connection.

## Switching Rules

Always include `--build` after changing profiles because all `VITE_*` values
are compiled into the frontend image.

Check the effective Compose configuration before startup:

```bash
docker compose --env-file frontend/.env.local config
```

Confirm the active backend mode after startup:

```bash
docker compose exec backend python -c "from app.core.config import settings; print(settings.APP_MODE, settings.POS_DEPLOYMENT_PROFILE, settings.DATABASE_URL)"
```

See
[`docs/architecture/unified-operational-runtime.md`](architecture/unified-operational-runtime.md)
for the feature-flag contract and alias migration rules.
