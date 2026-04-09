# Windows Local Deployment Runbook

## Purpose

This guide is for the person installing and supporting Pharma POS AI on a client Windows machine.

The deployment goal is:
- one pharmacy installation per client site
- local PostgreSQL on the same machine
- local backend service
- frontend accessible from a desktop shortcut
- nightly backups enabled

## Intended Client Model

Each pharmacy should have:
- its own database
- its own secrets
- its own backup set
- its own admin account

Do not clone one pharmacy database into another live client installation.

## Current Reality

This repo already includes:
- Windows backup script: [backup.bat](/home/grejoy/Projects/pharma-pos-ai/backup.bat)
- Windows backup task helper: [install_backup_task.bat](/home/grejoy/Projects/pharma-pos-ai/install_backup_task.bat)
- Windows restore script: [restore.bat](/home/grejoy/Projects/pharma-pos-ai/restore.bat)
- installer draft: [installer.iss](/home/grejoy/Projects/pharma-pos-ai/installer.iss)
- environment helper: [setup-env.bat](/home/grejoy/Projects/pharma-pos-ai/setup-env.bat)
- local launcher: [start.bat](/home/grejoy/Projects/pharma-pos-ai/start.bat)
- local shutdown helper: [stop.bat](/home/grejoy/Projects/pharma-pos-ai/stop.bat)
- admin backup status and local diagnostics in the `Settings` page

Still required for a stronger production installer:
- first-run admin provisioning
- reliable backend service registration
- cleaner release packaging without demo/default material

Current first-run admin tool:
- [provision-admin.bat](/home/grejoy/Projects/pharma-pos-ai/provision-admin.bat)
- [scripts/provision_admin.py](/home/grejoy/Projects/pharma-pos-ai/scripts/provision_admin.py)

## Pre-Install Checklist

Before installation, confirm:

- target machine is stable and supported
- Windows user with admin rights is available
- PostgreSQL installer is available
- `pg_dump`, `pg_restore`, and `psql` will be in `PATH`
- pharmacy name and installation path are known
- backup folder location is chosen
- strong `SECRET_KEY` is prepared
- strong PostgreSQL password is prepared
- initial admin username and password are prepared

## Standard Installation Target

Recommended target:

- App root: `C:\Program Files\Pharma-POS-AI`
- Database host: `localhost`
- Database port: `5432`
- Database name: `pharma_pos`
- Database user: `pharma_user`
- Backups folder: `C:\Program Files\Pharma-POS-AI\backups`

## Installation Procedure

### 1. Install PostgreSQL

Use official PostgreSQL for Windows.

During installation:
- keep the local service enabled
- record the superuser password
- ensure command-line tools are installed

### 2. Create App Database And App User

Using `psql` or SQL Shell:

```sql
CREATE USER pharma_user WITH PASSWORD 'strong_password_here';
CREATE DATABASE pharma_pos OWNER pharma_user;
GRANT ALL PRIVILEGES ON DATABASE pharma_pos TO pharma_user;
```

### 3. Deploy Application Files

Install or copy the application to:

- `C:\Program Files\Pharma-POS-AI`

### 4. Configure Environment

Run:

```bat
setup-env.bat
```

This will prepare:

- `backend\.env`
- `frontend\.env.local`

The script prompts for:

- pharmacy name
- PostgreSQL password for `pharma_user`

Then review the local values in:

- `backend\.env`

Minimum values:

```env
DATABASE_BACKEND=postgresql
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=pharma_pos
POSTGRES_USER=pharma_user
POSTGRES_PASSWORD=strong_password_here
SECRET_KEY=generated_secret_here
```

### 5. Initialize Database

Run migrations from the installed root.

If sample data is needed only for demonstration, seed intentionally.

Do not ship demo users in a client release unless the client explicitly requested a demo environment.

### 5A. Provision The First Admin

Run:

```bat
provision-admin.bat
```

Create the pharmacy-specific administrator account before handing the system to the client.

### 6. Configure Application Startup

The backend should run automatically at startup.

Preferred supportable options:
- Windows service for the backend
- desktop shortcut or local launcher for the frontend

Expected outcome:
- after machine reboot, backend is available without manual terminal steps

### 7. Configure Backups

Minimum expectation:
- nightly backup scheduled automatically
- backup files written to local backup folder
- technician knows restore procedure

Current script available:
- [backup.bat](/home/grejoy/Projects/pharma-pos-ai/backup.bat)

Windows task helper:
- [install_backup_task.bat](/home/grejoy/Projects/pharma-pos-ai/install_backup_task.bat)

Current restore tool:
- [restore.bat](/home/grejoy/Projects/pharma-pos-ai/restore.bat)

### 8. Validate Before Handover

Test:
- login works for the created admin account
- POS opens correctly
- products page loads
- product creation works
- stock receipt works
- sale completes
- sale void or refund is verified with a test invoice
- closeout summary is reviewed
- manual backup succeeds
- backup file appears in backup folder
- `Settings` shows database connected and recent backup status

## Client Handover Checklist

Before leaving the pharmacy:

- [ ] admin login verified
- [ ] cashier login verified
- [ ] POS sale verified
- [ ] product add/receive workflow verified
- [ ] sale reversal workflow verified
- [ ] closeout totals reviewed
- [ ] backup location shown to client
- [ ] backup procedure explained
- [ ] support contact recorded
- [ ] installed version recorded

## Upgrade Procedure

Before any upgrade:

1. create manual backup
2. confirm backup file exists
3. stop backend service if required
4. apply update
5. run migrations
6. start service
7. verify login, products, and POS

## Restore Procedure

Use:

- [restore.bat](/home/grejoy/Projects/pharma-pos-ai/restore.bat)

Rules:
- always create a fresh backup before restore
- confirm all users are out of the system
- restore only with technician/admin approval
- test login and a sample workflow after restore

## Support Record Template

For each client, record:

- pharmacy name
- machine name
- install path
- database name
- backup folder
- admin username
- installed version
- install date
- last successful backup test date
- last successful restore rehearsal date

## Operational Standard

Do not consider a Windows local deployment complete until:
- startup works after reboot
- backup runs reliably
- restore is documented
- admin can operate the system without terminal commands
