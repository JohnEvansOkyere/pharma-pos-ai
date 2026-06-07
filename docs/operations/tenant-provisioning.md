# Isolated Tenant Provisioning

## Purpose

`backend/scripts/provision_tenant.py` is the canonical provisioning command for
one isolated pharmacy deployment. It coordinates:

1. globally stable organization, branch, deployment, and device UUIDs
2. a dedicated tenant PostgreSQL database
3. Alembic migration to the repository head
4. matching organization, branch, device, and organization-level admin rows in
   the tenant database
5. matching organization, branch, and device registration in the central
   control plane
6. a unique application secret and per-device central-publish token
7. an optional dedicated Render backend service

The command is resumable. It records non-secret progress and generated
credentials under the ignored `var/provisioning/<tenant-slug>/` directory.
Both files use owner-only `0600` permissions. Preserve that directory until
provisioning and credential delivery are verified.

## Safety Rules

- Run the command from a trusted vendor workstation, never a pharmacy client.
- Supply database URLs and provider API keys through environment variables so
  they do not appear in shell history or process arguments.
- Do not delete the state directory during a partial run. It contains the UUIDs
  and token needed to resume without creating duplicate identities.
- The tool never auto-deletes partially created infrastructure.
- Render's free Postgres plan is rejected for production tenants.
- Render external database access is limited to one exact provisioner IP and is
  disabled after the tenant is migrated, seeded, registered, and deployed.
- Deliver the generated admin password separately from installation details.

## Render-Hosted Tenant

Required environment:

```bash
export CONTROL_PLANE_DATABASE_URL='postgresql://...central-control-plane...'
export RENDER_API_KEY='...'
export RENDER_OWNER_ID='tea-...'
export RENDER_REGION='frankfurt'
export RENDER_PROVISIONER_CIDR='203.0.113.8/32'
export TENANT_CORS_ORIGINS='https://tenant-pos.example.com'
export CENTRAL_INGEST_URL='https://pharma-pos-ai.onrender.com/api/sync/ingest'
export TENANT_SECRETS_FILE='/secure/vendor-secrets/example-pharmacy.json'
```

The tenant secrets file must be owner-only:

```bash
chmod 600 "$TENANT_SECRETS_FILE"
```

Africa's Talking example schema:

```json
{
  "SMS_PROVIDER": "africas_talking",
  "SMS_API_KEY": "<tenant-specific-key>",
  "SMS_USERNAME": "<tenant-specific-username>",
  "SMS_SENDER_ID": "<approved-sender-id>"
}
```

Hubtel example schema:

```json
{
  "SMS_PROVIDER": "hubtel",
  "SMS_CLIENT_ID": "<tenant-specific-client-id>",
  "SMS_CLIENT_SECRET": "<tenant-specific-client-secret>",
  "SMS_FROM_NUMBER": "<registered-number>",
  "SMS_SENDER_ID": "<approved-sender-id>"
}
```

Optional tenant-specific OpenAI, Anthropic, Groq, SMTP, and Telegram
credentials may be placed in the same owner-only file using the documented
backend environment names. Reserved deployment values such as `DATABASE_URL`,
`SECRET_KEY`, and `CLOUD_SYNC_API_TOKEN` are rejected because the provisioner
and infrastructure provider own them.

Dry run and allocate resumable identity:

```bash
cd backend
python scripts/provision_tenant.py \
  --organization-name 'Example Pharmacy' \
  --branch-name 'Main Branch' \
  --branch-code MAIN \
  --admin-username owner \
  --admin-email owner@example.com \
  --admin-full-name 'Example Owner' \
  --render
```

Apply the same recorded plan:

```bash
python scripts/provision_tenant.py \
  --organization-name 'Example Pharmacy' \
  --branch-name 'Main Branch' \
  --branch-code MAIN \
  --admin-username owner \
  --admin-email owner@example.com \
  --admin-full-name 'Example Owner' \
  --render \
  --apply
```

The Render path creates a paid isolated Postgres instance, waits for it to
become available, migrates and seeds it through the temporarily allowlisted
external connection, registers the control-plane rows, creates a dedicated
backend service using the internal database URL, and disables external database
access.

Hosted apply refuses `SMS_PROVIDER=stub`, missing provider credentials, broad
secret-file permissions, or a sensitive key fingerprint already assigned to
another tenant state under the canonical provisioning root.

The service uses:

- `APP_MODE=operational_pos`
- `POS_DEPLOYMENT_PROFILE=hosted`
- one tenant-specific `DATABASE_URL`
- one tenant-specific `SECRET_KEY`
- one per-device central-publish token
- the control-plane UUID identity envelope
- `python -m alembic upgrade head` as the pre-deploy migration command

## Existing Or Offline PostgreSQL

For a database created by local installation tooling or another provider, pass
its URL explicitly:

```bash
export CONTROL_PLANE_DATABASE_URL='postgresql://...central-control-plane...'
export TENANT_DATABASE_URL='postgresql://...isolated-tenant...'

cd backend
python scripts/provision_tenant.py \
  --organization-name 'Example Pharmacy' \
  --branch-name 'Main Branch' \
  --branch-code MAIN \
  --admin-username owner \
  --admin-email owner@example.com \
  --admin-full-name 'Example Owner' \
  --apply
```

This path migrates and seeds the supplied isolated database and registers it in
the control plane. Infrastructure creation remains the responsibility of the
offline installer or external provider.

## Completion Evidence

After a successful run, retain:

- `state.json`: UUIDs, provider resource IDs, completed steps, and local/central
  database row IDs
- `secrets.json`: generated application secret, sync token, and initial admin
  password
- Render database and service dashboard links
- successful backend health check
- successful first admin login
- first accepted heartbeat or business event in the central control plane

`secrets.json` is not a long-term password manager. After credential delivery,
move required recovery material into the approved vendor secret store and
remove unneeded local copies according to the secrets runbook.

## Provider References

- [Render API](https://render.com/docs/api)
- [Create Postgres API](https://api-docs.render.com/reference/create-postgres)
- [Postgres connection-info API](https://api-docs.render.com/reference/retrieve-postgres-connection-info)
- [Create service API](https://api-docs.render.com/reference/create-service)
- [Render Postgres networking](https://render.com/docs/databases)
