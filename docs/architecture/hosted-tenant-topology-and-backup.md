# Hosted Tenant Topology And Backup Decision

## Status

Accepted on 2026-06-07 for the initial fleet of roughly ten pharmacy clients.

This decision applies to hosted city pharmacies. Offline village pharmacies
continue to run PostgreSQL and the application backend on site.

## Provider And Isolation Boundary

Each hosted pharmacy organization receives:

- one paid Render Postgres instance used only by that organization
- one Render backend service using the shared versioned application image
- one tenant-specific `DATABASE_URL`
- tenant-specific application, messaging, and central-publish secrets

Branches belonging to the same pharmacy organization share that operational
database. Different pharmacy organizations never share an operational database
instance.

The existing Supabase project is retained only for the central reporting and
control-plane database. It is not an operational POS database for hosted
pharmacies. The vendor reporting backend reads this central database; it does
not fan out to tenant databases during user requests.

## Why Render Postgres

The application backend already runs on Render. A paid Render Postgres database
provides a separate recovery boundary per instance, continuous point-in-time
recovery, and logical exports. Render restores PITR data into a new database
instance, which allows validation before the tenant backend is switched.

This is a better initial fit than Supabase project-per-tenant because Supabase
PITR is a separate paid add-on for every project. Supabase remains suitable for
the central reporting database, where the existing ingestion and projection
schema already runs.

No free database tier is permitted for production tenant data. The initial
compute size must be load-tested before rollout and increased when connection,
memory, or latency measurements require it.

## Deployment Shape

```text
Hosted pharmacy A                       Hosted pharmacy B
Render backend A                        Render backend B
        |                                       |
Render Postgres A                       Render Postgres B
        |                                       |
        +---------- transactional outbox -------+
                              |
                              v
                 Central ingestion backend
                              |
                              v
             Supabase reporting/control database
```

Tenant backends publish central events asynchronously from the transactional
outbox. Central reporting failure must never roll back or block an operational
sale.

## Backup Mechanism

Every hosted tenant database uses two independent backup layers:

1. Render point-in-time recovery for short-window operational recovery.
2. Scheduled encrypted `pg_dump` logical backups copied to vendor-controlled
   object storage outside Render for longer retention, offboarding, and
   provider-independent recovery.

Baseline logical-backup retention:

- daily backups: 35 days
- monthly backups: 12 months

The backup job must encrypt before upload, record tenant ID, database identifier,
application version, schema revision, backup timestamp, size, and checksum, and
must alert on failure or staleness. Encryption keys must not be stored with the
backup objects.

The central reporting/control database follows the same off-platform logical
backup rule in addition to Supabase-managed project backups.

## Restore Acceptance Test

A backup mechanism is not complete until a real restore drill proves all of the
following:

1. Restore one tenant into a new isolated database instance.
2. Verify the backup checksum before restore.
3. Run Alembic schema checks and application health checks.
4. Verify user login, completed-sale totals, batch stock, movement-ledger
   consistency, and audit-chain integrity.
5. Confirm the other tenant databases and the central database were not changed.
6. Record recovery point, recovery duration, operator, result, and evidence.
7. Switch no production connection until validation passes.

For PITR incidents, recover to a new Render database and update only the affected
tenant backend's secret after validation. Preserve the original database until
the recovery is accepted.

## Recovery Targets

The short-window recovery point is bounded by Render's active PITR window. The
off-platform logical backup has a maximum one-day recovery-point objective until
more frequent exports are implemented and measured. No stronger RPO or RTO may
be promised to clients before a timed restore drill proves it.

## Source References

- [Render Postgres recovery and backups](https://render.com/docs/postgresql-backups)
- [Render Postgres plans and PITR](https://render.com/pricing)
- [Supabase database backups](https://supabase.com/docs/guides/platform/backups)
- [Supabase project database model](https://supabase.com/docs/guides/platform)

