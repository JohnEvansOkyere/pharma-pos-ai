# Hosted Tenant Backups

## Scope

Every hosted pharmacy has two recovery layers:

1. Render Postgres point-in-time recovery
2. encrypted logical backups in vendor-controlled S3-compatible storage outside
   Render

`backend/scripts/backup_tenant.py` runs as a dedicated Render cron service for
each tenant. The provisioner creates that cron job with the same internal
tenant database URL used by the operational backend.

## Backup Process

Each run:

1. reads the tenant's Alembic revision
2. runs `pg_dump` in PostgreSQL custom format
3. calculates the plaintext SHA-256 checksum
4. encrypts the dump with the tenant's unique AES-256-GCM key
5. calculates the encrypted SHA-256 checksum
6. uploads the encrypted object and a non-secret JSON manifest
7. creates a monthly copy on the first day of each month
8. prunes expired daily and monthly objects

Plaintext dumps exist only inside a temporary job directory and are removed
when the job exits.

## Object Layout

```text
tenants/<organization-uuid>/daily/YYYY/MM/<timestamp>-<revision>.dump.enc
tenants/<organization-uuid>/daily/YYYY/MM/<timestamp>-<revision>.dump.enc.json
tenants/<organization-uuid>/monthly/YYYY/MM/<timestamp>-<revision>.dump.enc
tenants/<organization-uuid>/monthly/YYYY/MM/<timestamp>-<revision>.dump.enc.json
```

Baseline retention:

- daily: 35 days
- monthly: 366 days

The storage access key must be restricted to the tenant prefix where the
provider supports prefix-scoped policies. It needs object put, list, and delete
rights for upload and retention pruning. Do not reuse storage access keys
between tenants.

## Encryption Format

The encrypted object contains:

- a versioned Pharma POS backup magic header
- an authenticated JSON header
- AES-256-GCM ciphertext
- the GCM authentication tag

The authenticated header records:

- backup ID
- organization UUID
- schema revision
- database name
- creation time
- PostgreSQL dump format
- plaintext checksum

The manifest adds encrypted checksum, encrypted size, and object key. Neither
the object nor manifest contains the database password or encryption key.

## Required Cron Environment

```env
DATABASE_URL=<tenant-internal-render-postgres-url>
CLOUD_SYNC_ORGANIZATION_UID=<tenant-uuid>
BACKUP_ENCRYPTION_KEY=<tenant-unique-generated-key>
BACKUP_S3_BUCKET=<bucket>
BACKUP_S3_ENDPOINT_URL=<s3-compatible-endpoint>
BACKUP_S3_REGION=<region>
BACKUP_S3_ACCESS_KEY_ID=<tenant-scoped-access-key>
BACKUP_S3_SECRET_ACCESS_KEY=<tenant-scoped-secret>
BACKUP_DAILY_RETENTION_DAYS=35
BACKUP_MONTHLY_RETENTION_DAYS=366
```

These values belong only on the backup cron service. Backup storage and
encryption credentials are deliberately excluded from the operational web
backend environment.

## Manual Verification

From a trusted environment with the same variables:

```bash
cd backend
python scripts/backup_tenant.py
```

Success prints one JSON result containing the object key, checksums, schema
revision, size, and retention deletions. Also verify the encrypted object and
manifest exist in storage.

Automation is not restore proof. The separate restore-drill checklist item
remains open until one real encrypted object is downloaded, decrypted, restored
into a new isolated database, and validated without changing another tenant.
