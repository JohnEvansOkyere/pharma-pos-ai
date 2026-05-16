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

## Deployment Model

**Primary path: Docker Compose.**

All three services — PostgreSQL, backend API, and frontend — run as Docker containers managed by `docker-compose.yml`. This is the standard production deployment. It requires only Docker Desktop on the client machine; no separate Python, Node.js, or PostgreSQL installation is needed.

The `start.bat` / `stop.bat` scripts are a secondary option for developer or bare-metal setups that require a local Python virtual environment and a pre-built frontend. Do not use them for client installs unless Docker Desktop cannot be installed.

## Available Scripts

- `setup-env.bat` — creates `backend/.env` and `frontend/.env.local` from the `.env.example` template
- `start.bat` — bare-metal launcher (local Python path only; not needed for Docker)
- `stop.bat` — stops bare-metal launcher windows
- `backup.bat` — runs a `pg_dump` backup of the local PostgreSQL database
- `install_backup_task.bat` — registers `backup.bat` as a Windows Scheduled Task
- `restore.bat` — restores a backup file into the database
- `provision-admin.bat` — creates the first admin account
- `uninstall-app.bat` — removes the application

## Pre-Install Checklist

Before arriving at the client site, confirm:

- [ ] Target machine is stable with Windows 10 64-bit or newer
- [ ] Windows user with administrator rights is available for the install session
- [ ] Docker Desktop for Windows installer is downloaded and ready
- [ ] WSL 2 is enabled (required by Docker Desktop) — check in Windows Features
- [ ] Project files are copied to the machine (USB drive, local copy, or git clone)
- [ ] Pharmacy name is known
- [ ] Strong PostgreSQL password is prepared (write it down securely)
- [ ] Strong admin account username and password are prepared
- [ ] Backup folder location is decided (`C:\PharmaBackups` is a safe default)
- [ ] Windows Defender / antivirus exclusions planned for the install folder

## Standard Installation Target

- App root: `C:\Pharma-POS-AI`
- Database host: `db` (Docker internal) / `localhost:5435` (host-side access)
- Database name: `pharma_pos`
- Database user: `pharma_user`
- Backups folder: `C:\PharmaBackups`
- Frontend URL: `http://localhost:8080`
- Backend API URL: `http://localhost:8000`

## Installation Procedure

### 1. Enable WSL 2

Open PowerShell as Administrator and run:

```powershell
wsl --install
```

Restart the machine if prompted. WSL 2 is required by Docker Desktop.

### 2. Install Docker Desktop

Download and install Docker Desktop for Windows. During installation:
- enable WSL 2 backend when prompted
- do not enable Kubernetes (not needed)

After installation, start Docker Desktop and wait until the whale icon in the system tray shows "Docker Desktop is running".

Verify in a Command Prompt:

```cmd
docker --version
docker compose version
```

Both commands must succeed before continuing.

### 3. Deploy Application Files

Copy or clone the project to the target path:

```
C:\Pharma-POS-AI
```

Verify the folder contains `docker-compose.yml`, `backend\`, `frontend\`, `setup-env.bat`, and `backup.bat`.

### 4. Configure Environment

Open a Command Prompt in `C:\Pharma-POS-AI` and run:

```bat
setup-env.bat
```

Enter the pharmacy name and the PostgreSQL password when prompted. The script generates a strong `SECRET_KEY` automatically and writes `backend\.env`.

After the script finishes, open `backend\.env` and confirm:

```env
POSTGRES_PASSWORD=<the password you entered — not empty>
SECRET_KEY=<a long generated string — not a placeholder>
ENVIRONMENT=production
APP_NAME=<the pharmacy name you entered>
```

### 5. Start Docker Services

From `C:\Pharma-POS-AI` run:

```cmd
docker compose up -d
```

This builds the backend and frontend images and starts all three containers (database, backend, frontend). First run takes 3–5 minutes while images build.

Check that all containers are running:

```cmd
docker compose ps
```

All three services (`pharma-pos-db`, `pharma-pos-backend`, `pharma-pos-frontend`) should show `Up` or `healthy`.

If the backend shows `unhealthy`, wait 60 seconds and check again — it waits for the database to be ready.

### 6. Run Database Migrations

After the containers are healthy, apply any pending schema migrations:

```cmd
docker exec pharma-pos-backend alembic upgrade head
```

This is safe to run on every install and on every upgrade.

### 7. Provision The First Admin Account

Run the provisioning script inside the backend container:

```cmd
docker exec -it pharma-pos-backend python scripts/provision_admin.py
```

Enter the admin username, email, full name, and password when prompted. This creates the first administrator account for this pharmacy. No other accounts should be created at this stage — the admin creates staff accounts from within the application.

> **Do not use generic or shared passwords.** The admin password must be strong and known only to the pharmacy owner.

### 8. Verify The Application Is Running

Open a browser and go to:

```
http://localhost:8080
```

Log in with the admin account created in step 7. Confirm:
- dashboard loads without errors
- products page is accessible
- POS page opens

### 9. Configure Windows Firewall (If Needed)

By default, ports 8080 and 8000 are accessible only from `localhost`. If pharmacy staff will access the system from other computers on the same local network, open inbound rules in Windows Defender Firewall for TCP port 8080.

If access is limited to the single pharmacy workstation, no firewall changes are needed.

### 10. Configure Automatic Startup

Docker Desktop is configured to start automatically at Windows login by default. The containers have `restart: unless-stopped`, so they restart automatically after a reboot.

Verify after a reboot:
1. Wait for Docker Desktop to show "running" in the system tray
2. Open `http://localhost:8080` — it should load without manual intervention

### 11. Configure Backups

Open a Command Prompt in `C:\Pharma-POS-AI` as Administrator and run:

```bat
install_backup_task.bat
```

This registers a Windows Scheduled Task that runs `backup.bat` every night. Backup files are written to the `backups\` folder inside the project directory.

> **Important:** `backup.bat` connects to PostgreSQL at port `5435` when using Docker Compose (the database container maps to host port 5435). Confirm `backup.bat` is using the correct port — see the Docker Backup Note below.

After installing the task, run a manual backup to confirm it works:

```bat
backup.bat
```

A `.dump` file should appear in the `backups\` folder.

#### Docker Backup Note

When running under Docker Compose, PostgreSQL is reachable from the host at port `5435`. The `backup.bat` script reads `POSTGRES_PORT` from `backend\.env`. If `POSTGRES_PORT=5432` is set in `.env` (the Docker internal port), backup will fail.

**Workaround:** After confirming the application is running, update `POSTGRES_PORT` in `backend\.env` to `5435` before running `backup.bat`. This affects only host-side tools like `pg_dump`; Docker Compose overrides this value internally for the backend container.

Alternatively, run `pg_dump` directly inside the database container (no extra installation required):

```cmd
docker exec pharma-pos-db pg_dump -U pharma_user -d pharma_pos -F c -f /tmp/backup.dump
docker cp pharma-pos-db:/tmp/backup.dump C:\PharmaBackups\pharma_backup_%DATE:~-4%%DATE:~3,2%%DATE:~0,2%.dump
```

### 12. Validate Before Handover

Test every workflow before leaving the pharmacy:
- login works for the created admin account
- POS opens correctly
- products page loads
- product creation works
- stock receipt works
- sale completes
- sale void or refund is verified with a test invoice
- closeout summary is reviewed
- manual backup succeeds and the `.dump` file appears
- `Settings` page shows database connected and recent backup status
- machine rebooted and system came back up without manual steps

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
