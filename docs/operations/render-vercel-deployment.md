# Render And Vercel Deployment

## Deployment Boundaries

Render hosts two different backend roles:

- one central `cloud_reporting` backend connected to the existing Supabase
  reporting/control-plane database
- one dedicated `operational_pos` backend and paid Render Postgres instance for
  each hosted pharmacy organization

Different pharmacy organizations never share an operational database. Vercel
serves browser frontends only and must never receive backend secrets.

## Central Reporting Backend

The root `render.yaml` describes the central reporting service. Its required
settings include:

```env
DATABASE_BACKEND=postgresql
DATABASE_URL=postgresql://...central-supabase...
SECRET_KEY=<unique-central-secret>
ENVIRONMENT=production
APP_MODE=cloud_reporting
DEBUG=false
BACKEND_CORS_ORIGINS=https://pharma-pos-ai.vercel.app
CLOUD_SYNC_REQUIRE_TOKEN=true
CLOUD_PROJECTION_ENABLED=true
```

Apply central schema migrations from a trusted machine:

```bash
cd backend
DATABASE_URL='postgresql://...central-supabase...' \
SECRET_KEY='temporary-valid-tooling-secret-0000000000' \
ENVIRONMENT=development \
python -m alembic upgrade head
```

The central service stores control-plane registrations, accepted events, cloud
projections, vendor dashboards, and fleet AI data. It is not a hosted till.

## Hosted Pharmacy Backend

Use [Isolated Tenant Provisioning](tenant-provisioning.md). The provisioner
creates:

- one paid Render Postgres instance for the pharmacy organization
- one Render backend service connected through the database's internal URL
- matching tenant/control-plane UUID identity
- a scoped organization admin
- a unique `SECRET_KEY` and central-publish token

The hosted runtime uses:

```env
APP_MODE=operational_pos
POS_DEPLOYMENT_PROFILE=hosted
CLOUD_SYNC_ENABLED=true
CLOUD_PROJECTION_ENABLED=false
```

Tenant migrations run before deployment. Operational writes commit to the
tenant database and transactional outbox first; central availability never
controls whether a sale succeeds.

## Offline Pharmacy Sync

Offline installations keep PostgreSQL and the backend on site. Register their
device through the control plane and configure the complete generated identity
block:

```env
APP_MODE=operational_pos
POS_DEPLOYMENT_PROFILE=offline
CLOUD_SYNC_ENABLED=true
CLOUD_SYNC_INGEST_URL=https://pharma-pos-ai.onrender.com/api/sync/ingest
CLOUD_SYNC_API_TOKEN=<per-device-token>
CLOUD_SYNC_ORGANIZATION_ID=<central-legacy-id>
CLOUD_SYNC_BRANCH_ID=<central-legacy-id>
CLOUD_SYNC_ORGANIZATION_UID=<control-plane-uuid>
CLOUD_SYNC_BRANCH_UID=<control-plane-uuid>
CLOUD_SYNC_DEPLOYMENT_UID=<control-plane-uuid>
CLOUD_SYNC_DEVICE_UID=<control-plane-device-uuid>
```

The UUID envelope is authoritative. Numeric organization and branch values
remain only for compatibility with older clients.

## Vercel Frontends

Only browser-safe values belong in Vercel:

```env
VITE_API_URL=https://the-correct-backend.example.com/api
VITE_APP_MODE=cloud_reporting
```

The central vendor portal uses `cloud_reporting`. A hosted pharmacy frontend
must target that pharmacy's dedicated operational backend and use the
operational frontend profile. Do not place database URLs, application secrets,
sync tokens, AI keys, SMTP credentials, or Telegram tokens in `VITE_*`
variables.

## Verification

For every deployment:

1. Alembic reports the repository head.
2. `/health` confirms database connectivity.
3. The expected app mode and deployment profile appear in diagnostics.
4. The initial admin can log in only to the intended tenant.
5. A sale remains successful if central reporting is unavailable.
6. The outbox later uploads with the registered UUID identity.
7. The central command center shows the first heartbeat/event under the correct
   organization and branch.
