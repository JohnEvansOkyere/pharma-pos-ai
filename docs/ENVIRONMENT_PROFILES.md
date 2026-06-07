# Docker Environment Profiles

The source-built Docker setup keeps backend and frontend profiles in their own
application directories:

| Backend profile | Frontend profile | Runtime mode | Database |
| --- | --- | --- | --- |
| `backend/.env_local` | `frontend/.env_local` | `local_pos` | Local Docker PostgreSQL |
| `backend/.env_cloud` | `frontend/.env_cloud` | `online_pos` | Managed cloud PostgreSQL |

`cloud_reporting` remains a third, separate mode for the vendor reporting
portal. It is not the city pharmacy POS mode.

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
APP_MODE=online_pos
DATABASE_URL=postgresql://USER:PASSWORD@HOST:6543/DATABASE
SECRET_KEY=<the cloud backend JWT secret>
```

The matching `frontend/.env_cloud` contains:

```env
VITE_API_URL=/api
VITE_APP_MODE=online_pos
```

## Select Local/Village Mode

```bash
cp backend/.env_local backend/.env
cp frontend/.env_local frontend/.env.local
docker compose --env-file frontend/.env.local up -d --build
```

The backend uses the local `db` service and the frontend is built in
`local_pos` mode.

## Select Cloud/City Mode

```bash
cp backend/.env_cloud backend/.env
cp frontend/.env_cloud frontend/.env.local
docker compose --env-file frontend/.env.local up -d --build
```

The backend still runs in local Docker, but connects through `DATABASE_URL` to
the cloud PostgreSQL server. The frontend is rebuilt in `online_pos` mode and
calls the local backend through the Nginx `/api` proxy.

The compose file currently starts the local PostgreSQL container in both
profiles. In cloud mode that container is unused; `DATABASE_URL` controls the
backend's real database connection.

## Switching Rules

Always include `--build` after changing profiles because `VITE_APP_MODE` and
`VITE_API_URL` are compiled into the frontend image.

Check the effective Compose configuration before startup:

```bash
docker compose --env-file frontend/.env.local config
```

Confirm the active backend mode after startup:

```bash
docker compose exec backend python -c "from app.core.config import settings; print(settings.APP_MODE, settings.DATABASE_URL)"
```

Do not use `online_pos` for a client rollout until the unresolved tenant
isolation findings in `MEMORY.md` (`ONLINE-P0-01` through `ONLINE-P0-04`) are
fixed. The profile is suitable for controlled development and testing.
