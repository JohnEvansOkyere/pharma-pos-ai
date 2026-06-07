# Secrets And Environment Management

## Rule

Secrets belong server-side. Do not commit real `.env` files, API keys, database passwords, SMTP passwords, Telegram tokens, or cloud sync tokens.

Each isolated hosted pharmacy must have its own:

- Render Postgres connection credential
- application `SECRET_KEY`
- central-publish token
- messaging-provider credentials
- optional AI, SMTP, and Telegram credentials when those integrations are
  enabled

Do not reuse these values across tenant backends.

## Backend Environment

Backend environment belongs in `backend/.env`.

Examples:

- `DATABASE_URL`
- `POSTGRES_HOST`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `SECRET_KEY`
- `CLOUD_SYNC_INGEST_URL`
- `CLOUD_SYNC_API_TOKEN`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GROQ_API_KEY`
- `SMTP_HOST`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `TELEGRAM_BOT_TOKEN`

## Provisioning Secret Bundle

Full tenant provisioning reads operator-supplied integration credentials from
an owner-only JSON file selected by `TENANT_SECRETS_FILE`. The file must have no
group or other permissions; `0600` is the expected mode.

The provisioner:

- generates a unique application secret, publish token, and initial admin
  password
- obtains the unique database URL from the dedicated database provider
- validates provider-specific SMS fields
- rejects reserved deployment variables in the operator file
- rejects sensitive credential fingerprints already present in another tenant
  state under `var/provisioning/`
- stores plaintext only in ignored owner-only `secrets.json`
- stores one-way fingerprints, never plaintext credentials, in resumable
  `state.json`
- injects runtime values directly into the dedicated Render service

Hosted provisioning requires a real SMS provider. Supported required sets:

- Africa's Talking: `SMS_API_KEY`, `SMS_USERNAME`, `SMS_SENDER_ID`
- Hubtel: `SMS_CLIENT_ID`, `SMS_CLIENT_SECRET`, `SMS_FROM_NUMBER`,
  `SMS_SENDER_ID`

Hosted bundles also require tenant-scoped off-platform backup storage:

- `BACKUP_S3_BUCKET`
- `BACKUP_S3_ENDPOINT_URL`
- `BACKUP_S3_REGION`
- `BACKUP_S3_ACCESS_KEY_ID`
- `BACKUP_S3_SECRET_ACCESS_KEY`

The provisioner generates `BACKUP_ENCRYPTION_KEY` independently for each
tenant. Backup storage and encryption credentials are injected only into the
dedicated backup cron service, not the operational web backend.

`SMS_PROVIDER=stub` remains valid only for deployments where customer messaging
is intentionally disabled, such as a basic offline profile.

## Frontend Environment

Frontend environment belongs in `frontend/.env.local` or deployment equivalent.

The frontend should only need:

- public API base URL such as `VITE_API_URL`

Do not put Supabase service keys, OpenAI keys, Anthropic keys, Groq keys, SMTP credentials, or Telegram bot tokens in frontend env.

## Production Startup Requirements

Production settings enforce:

- PostgreSQL backend
- `SECRET_KEY` must be set
- unsupported database backends rejected

## Key Rotation

Operational key rotation should cover:

- JWT secret rotation plan
- cloud sync API token rotation
- database password rotation
- AI provider key rotation
- SMTP password rotation
- Telegram bot token rotation

Keep old tokens valid only long enough to roll devices safely.

Rotation is an audited operation, not a provisioning-state edit:

1. create the replacement credential in the provider
2. update the one affected tenant backend
3. verify login, messaging, sync, and health telemetry
4. revoke the old credential
5. update the vendor secret store and fingerprint record

Do not overwrite `var/provisioning/<tenant>/secrets.json` with different values
to bypass the provisioner's immutability check. Device publish tokens should be
rotated through the control-plane token-rotation workflow so the stored hash and
tenant backend change together.
