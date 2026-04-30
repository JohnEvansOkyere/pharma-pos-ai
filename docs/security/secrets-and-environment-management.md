# Secrets And Environment Management

## Rule

Secrets belong server-side. Do not commit real `.env` files, API keys, database passwords, SMTP passwords, Telegram tokens, or cloud sync tokens.

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
