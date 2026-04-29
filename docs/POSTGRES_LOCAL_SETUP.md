# Local PostgreSQL Setup Guide

## Purpose

This guide shows how to set up the backend to use local PostgreSQL instead of SQLite.

This is the recommended setup for real pharmacy deployments:

- PostgreSQL runs on the same local machine as the backend
- the backend connects to that local database
- the app works without internet

## Target Setup

- Database server: local PostgreSQL
- Database name: `pharma_pos`
- Database user: `pharma_user`
- Backend host: `localhost`
- Backend port: `5432`

## Environment Files Updated

These files now point to PostgreSQL:

- [backend/.env](/home/grejoy/Projects/pharma-pos-ai/backend/.env)
- [.env](/home/grejoy/Projects/pharma-pos-ai/.env)

Current connection settings:

```env
DATABASE_BACKEND=postgresql
DATABASE_URL=
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=pharma_pos
POSTGRES_USER=pharma_user
POSTGRES_PASSWORD=<set-a-strong-site-specific-password>
```

The application builds the final connection string from those values.

## 1. Install PostgreSQL

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

### Windows

Download PostgreSQL from:

- https://www.postgresql.org/download/windows/

During installation:

- keep port `5432`
- remember the PostgreSQL superuser password you choose

## 2. Start PostgreSQL

### Linux

```bash
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

### Windows

PostgreSQL usually starts automatically as a Windows service after installation.

## 3. Create The App User And Database

### Linux

Open PostgreSQL:

```bash
sudo -u postgres psql
```

Then run:

```sql
CREATE USER pharma_user WITH PASSWORD '<set-a-strong-site-specific-password>';
CREATE DATABASE pharma_pos OWNER pharma_user;
GRANT ALL PRIVILEGES ON DATABASE pharma_pos TO pharma_user;
\q
```

### Windows

Open:

- `SQL Shell (psql)`

Log in as the `postgres` superuser, then run:

```sql
CREATE USER pharma_user WITH PASSWORD '<set-a-strong-site-specific-password>';
CREATE DATABASE pharma_pos OWNER pharma_user;
GRANT ALL PRIVILEGES ON DATABASE pharma_pos TO pharma_user;
```

## 4. Confirm Database Access

Test the login:

```bash
psql -h localhost -p 5432 -U pharma_user -d pharma_pos
```

If prompted, enter:

Enter the same site-specific password you configured for `pharma_user`.

If it connects, PostgreSQL is ready.

## 5. Initialize The Schema

From the repo root:

```bash
cd /home/grejoy/Projects/pharma-pos-ai
bash scripts/init_db.sh
```

That runs:

- Alembic migrations

If you want seed/demo data too:

```bash
SEED_DATABASE=true bash scripts/init_db.sh
```

## 6. Run The Backend

From the backend directory:

```bash
cd /home/grejoy/Projects/pharma-pos-ai/backend
python -m app.main
```

Or:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 7. Run The Frontend

```bash
cd /home/grejoy/Projects/pharma-pos-ai/frontend
npm run dev
```

Frontend:

- http://localhost:3000

Backend:

- http://localhost:8000

## 8. How The Backend Chooses PostgreSQL

The backend settings now expect:

```env
DATABASE_BACKEND=postgresql
```

If `DATABASE_URL` is empty, the app builds this:

```text
postgresql://pharma_user:<site-specific-password>@localhost:5432/pharma_pos
```

## 9. Common Problems

### Problem: `password authentication failed`

Check:

- username is `pharma_user`
- password matches the one used when creating the PostgreSQL user
- `backend/.env` matches the database credentials

### Problem: `database "pharma_pos" does not exist`

Create it:

```sql
CREATE DATABASE pharma_pos OWNER pharma_user;
```

### Problem: backend still uses old SQLite settings

Check:

- [backend/.env](/home/grejoy/Projects/pharma-pos-ai/backend/.env)
- make sure the backend is started from the `backend/` directory
- restart the backend after any env change

### Problem: `connection refused`

Check:

- PostgreSQL service is running
- port `5432` is open locally
- host is `localhost`

## 10. Recommended Next Cleanup

Before client deployment, change:

- `POSTGRES_PASSWORD`
- `SECRET_KEY`

Do not use the current values for client production installs unchanged.

## Recommended Production Pattern

For a real client install:

- PostgreSQL on the main pharmacy PC
- backend on the same PC
- frontend opened locally or from LAN-connected PCs

That gives you:

- offline operation
- one source of truth for stock
- simpler backup and support
