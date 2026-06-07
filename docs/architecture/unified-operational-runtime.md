# Unified Operational Runtime

## Decision

Pharmacy deployments use one canonical application mode:

```env
APP_MODE=operational_pos
```

The deployment location is independent:

```env
POS_DEPLOYMENT_PROFILE=offline
# or
POS_DEPLOYMENT_PROFILE=hosted
```

`cloud_reporting` remains a separate central portal mode because it must reject
operational writes.

The legacy `local_pos` and `online_pos` values are accepted temporarily and
normalize to `operational_pos`. `local_pos` derives the offline profile and
`online_pos` derives the hosted profile. New deployments and documentation must
not use those aliases.

## Backend Feature Flags

| Setting | Purpose |
| --- | --- |
| `POS_DEPLOYMENT_PROFILE` | Selects hosted or on-site operational behavior |
| `CLOUD_SYNC_ENABLED` | Enables asynchronous delivery of the transactional outbox |
| `CLOUD_SYNC_INGEST_URL` | Selects the central event-publishing target |
| `CUSTOMER_RETENTION_ENABLED` | Enables post-sale customer-retention actions |
| `CUSTOMER_RECEIPTS_ENABLED` | Enables digital receipt dispatch |
| `CUSTOMER_FOLLOWUPS_ENABLED` | Enables follow-up creation and hourly dispatch |
| `CLOUD_PROJECTION_ENABLED` | Central `cloud_reporting` service only |

All operational deployments write outbox events in the same database
transaction as the business write. `CLOUD_SYNC_ENABLED` controls delivery, not
event creation. This keeps central-reporting downtime outside the sale
transaction for both hosted and offline pharmacies.

Hosted operational users must have organization and branch assignments.
Offline installations temporarily allow older unscoped users so installed
single-pharmacy databases can be migrated without blocking the till.

## Frontend Feature Flags

| Setting | Purpose |
| --- | --- |
| `VITE_POS_DEPLOYMENT_PROFILE` | Labels the build as hosted or offline |
| `VITE_CUSTOMER_RETENTION_ENABLED` | Shows customer, analytics, and follow-up routes |
| `VITE_OFFLINE_QUEUE_ENABLED` | Enables hosted connectivity monitoring and the browser queue |

These values are compiled into the frontend image. Rebuild the frontend after
changing them.

The browser queue is only a short network-drop buffer for hosted deployments.
It is not the offline architecture. Offline pharmacies reach a backend and
PostgreSQL instance running on site.

## Standard Profiles

Offline pharmacy:

```env
APP_MODE=operational_pos
POS_DEPLOYMENT_PROFILE=offline
CLOUD_SYNC_ENABLED=false
CUSTOMER_RETENTION_ENABLED=false
CUSTOMER_RECEIPTS_ENABLED=false
CUSTOMER_FOLLOWUPS_ENABLED=false
```

Hosted pharmacy:

```env
APP_MODE=operational_pos
POS_DEPLOYMENT_PROFILE=hosted
CLOUD_SYNC_ENABLED=true
CUSTOMER_RETENTION_ENABLED=true
CUSTOMER_RECEIPTS_ENABLED=true
CUSTOMER_FOLLOWUPS_ENABLED=true
```

Central reporting:

```env
APP_MODE=cloud_reporting
CLOUD_PROJECTION_ENABLED=true
```

## Migration Rule

Do not remove legacy aliases until existing environment files and deployed
services have been moved to the canonical settings. Removal is tracked
separately in Phase 10.10 of the go-live checklist.

