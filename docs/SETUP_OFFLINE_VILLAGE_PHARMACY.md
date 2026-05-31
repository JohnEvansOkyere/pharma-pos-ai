# SETUP GUIDE — Offline-First Village Pharmacy (local_pos)

**Mode:** `local_pos`  
**Use case:** Village or rural pharmacy with unreliable or no internet  
**Examples:** Brong-Ahafo, Northern Region, Eastern Region rural pharmacies  
**Audience:** You (the vendor/installer), not the pharmacy staff

---

## How This Mode Works

In `local_pos` mode:
- Everything runs **on the pharmacy's own machine** — no internet required for daily operation
- A local PostgreSQL database stores all sales, stock, and audit data
- Sales sync to the central cloud automatically when internet is available (via the outbox queue)
- If internet is never available, the pharmacy still operates fully — sync is optional
- The cloud dashboard is not accessible from this installation (no cloud data to show)
- No customer retention or SMS features (those require reliable internet)

> [!IMPORTANT]
> Data lives on the pharmacy's machine. If the machine dies and there is no backup, data is lost. The nightly backup schedule is **mandatory**, not optional.

---

## Regarding the Existing `CLIENT_INSTALLATION_PLAN.md`

There is already a high-level plan at `docs/CLIENT_INSTALLATION_PLAN.md` and a detailed technical runbook at `docs/WINDOWS_LOCAL_DEPLOYMENT_RUNBOOK.md`.

**This document is the practitioner-facing version** — written for the person doing the physical install, with every command in the order they are run. It incorporates the latest changes (Docker-based, `local_pos` mode, backup verification).

Use `WINDOWS_LOCAL_DEPLOYMENT_RUNBOOK.md` as the technical reference when debugging. Use this document when doing the actual install.

---

## What You Need Before the Site Visit

### 1. (Optional) Register the pharmacy for cloud sync

If this pharmacy will eventually sync data to the central cloud dashboard, run this on your laptop first:

```bash
cd /path/to/pharma-pos-ai/backend

DATABASE_URL="postgresql://postgres:PASSWORD@aws-1-eu-central-2.pooler.supabase.com:6543/postgres" \
  python scripts/provision_client.py
```

Enter the pharmacy name, branch name, and device name. The script prints:

```env
CLOUD_SYNC_ENABLED=true
CLOUD_SYNC_INGEST_URL=https://pharma-pos-ai.onrender.com/api/sync/ingest
CLOUD_SYNC_API_TOKEN=abcdef...
CLOUD_SYNC_DEVICE_UID=pos-001-uuid
CLOUD_SYNC_ORGANIZATION_ID=7
CLOUD_SYNC_BRANCH_ID=3
```

Save this block. If the pharmacy does not want cloud sync, skip this step entirely.

### 2. Prepare the installation USB / folder

Copy the release files to a USB stick:
```
docker-compose.client.yml
setup-env.bat
backup.bat
restore.bat
install_backup_task.bat
backend/.env.client.example
```

---

## On-Site Installation Steps

### Step 1 — Check the machine

Requirements:
- Windows 10 64-bit or newer
- At least 4 GB RAM (8 GB recommended)
- At least 20 GB free disk space (for database growth + backups)
- Power supply or UPS (power cuts are the biggest risk to data integrity)

> [!CAUTION]
> If the pharmacy has frequent power cuts and no UPS, strongly recommend installing a UPS before going live. An abrupt power cut during a database write can corrupt PostgreSQL. A UPS gives the system time to finish writing.

### Step 2 — Enable WSL 2 and install Docker Desktop

Open PowerShell as Administrator:

```powershell
wsl --install
```

Restart if prompted. Then download and install **Docker Desktop for Windows**:
- Enable WSL 2 backend during install
- Do not enable Kubernetes

Verify:

```cmd
docker --version
docker compose version
```

Both must return version numbers.

### Step 3 — Copy application files

Copy the release to:

```
C:\Pharma-POS-AI
```

Verify these files are present:
- `docker-compose.client.yml`
- `setup-env.bat`
- `backup.bat`
- `restore.bat`
- `install_backup_task.bat`
- `backend\.env.client.example`

### Step 4 — Authenticate with GitHub Container Registry

You need a GitHub PAT with `read:packages` scope.  
Generate at: `https://github.com/settings/tokens` → classic → tick **read:packages**.

```cmd
docker login ghcr.io -u JohnEvansOkyere -p YOUR_PAT_HERE
```

`Login Succeeded` must appear. Stored on the machine — does not need repeating on upgrades.

### Step 5 — Configure the environment

Open Command Prompt in `C:\Pharma-POS-AI` and run:

```bat
setup-env.bat
```

Enter the pharmacy name and a strong PostgreSQL password.

> [!WARNING]
> **Password rule:** Letters and numbers only. No `@`, `!`, `#`, `$`, `%`. Special characters break URL parsing inside Docker and cause backend failures that are hard to diagnose on-site.

After the script finishes, open `backend\.env` and confirm:

```env
APP_MODE=local_pos
DATABASE_BACKEND=postgresql
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=pharma_pos
POSTGRES_USER=pharma_user
POSTGRES_PASSWORD=<the password you entered>
SECRET_KEY=<a long generated string — not a placeholder>
ENVIRONMENT=production
DEBUG=false
ENABLE_BACKGROUND_SCHEDULER=true
```

**If cloud sync is enabled**, paste the block from Preparation Step 1 at the bottom:

```env
CLOUD_SYNC_ENABLED=true
CLOUD_SYNC_INGEST_URL=https://pharma-pos-ai.onrender.com/api/sync/ingest
CLOUD_SYNC_API_TOKEN=...
CLOUD_SYNC_DEVICE_UID=...
CLOUD_SYNC_ORGANIZATION_ID=7
CLOUD_SYNC_BRANCH_ID=3
```

**If cloud sync is not needed:**

```env
CLOUD_SYNC_ENABLED=false
```

### Step 6 — Start all services

```cmd
docker compose -f docker-compose.client.yml up -d
```

This starts three containers:
- `pharma-pos-db` — local PostgreSQL database
- `pharma-pos-backend` — FastAPI backend
- `pharma-pos-frontend` — nginx serving the React frontend

Wait 1–2 minutes (longer on first run — images are downloading). Then check:

```cmd
docker compose -f docker-compose.client.yml ps
```

All three must show `Up` or `healthy`. If the backend shows `unhealthy`, wait 60 seconds and check again.

### Step 7 — Run database migrations

```cmd
docker exec pharma-pos-backend alembic upgrade head
```

Runs all schema migrations against the local PostgreSQL. Safe to run on every install and upgrade.

### Step 8 — Create the admin account

```cmd
docker exec -it pharma-pos-backend python scripts/provision_admin.py
```

Enter:
- Username (e.g. `admin`)
- Email
- Full name (pharmacy owner's name)
- Password — make it strong; this is the owner's account

Record the credentials securely. The owner must change the password on first login.

### Step 9 — Verify the application

Open a browser and go to:

```
http://localhost:8080
```

Log in with the admin account. Run through:

- [ ] Dashboard loads
- [ ] Products page accessible — add one test product with a batch
- [ ] POS page: complete a test sale (cash payment)
- [ ] Sale appears in Sales list
- [ ] Stock Adjustments: receive stock, confirm quantities update
- [ ] Reboot the machine — system comes back automatically, login works

### Step 10 — Create desktop shortcut

```powershell
$s = "[InternetShortcut]`r`nURL=http://localhost:8080`r`nIconFile=C:\Pharma-POS-AI\PHARMACY.ico`r`nIconIndex=0"
$s | Out-File "$env:PUBLIC\Desktop\Pharma POS.url" -Encoding ASCII
```

### Step 11 — Set containers to auto-start

```cmd
docker update --restart always pharma-pos-db pharma-pos-backend pharma-pos-frontend
```

The system now starts automatically on every Windows boot.

### Step 12 — Install the nightly backup task

Open a Command Prompt **as Administrator** in `C:\Pharma-POS-AI`:

```bat
install_backup_task.bat
```

This installs a Windows scheduled task that runs `backup.bat` every night at 11:00 PM.

**Immediately run a manual backup to confirm it works:**

```bat
backup.bat
```

A `.dump` file must appear in `C:\Pharma-POS-AI\backups\` before you proceed. If the folder is empty, stop and diagnose before handing over.

### Step 13 — Open firewall (only if other machines need access)

If the pharmacy has more than one workstation:

```powershell
New-NetFirewallRule -DisplayName "Pharma POS" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow
```

Other machines on the same LAN can then access the system at:
```
http://192.168.x.x:8080
```
(replace with the server machine's IP address, shown by `ipconfig`).

---

## Handover Checklist

Do not leave until every item is ticked:

- [ ] Admin login works
- [ ] Cashier login works (create a cashier account in Settings → Users)
- [ ] POS sale completes end to end (cash payment)
- [ ] Stock adjustment (receive stock) works
- [ ] Machine rebooted — system came back up without manual steps
- [ ] Manual backup ran — `.dump` file visible in `backups\` folder
- [ ] Backup scheduled task confirmed active (`schtasks /query /tn "PharmaBackup"`)
- [ ] Desktop shortcut opens the app
- [ ] Pharmacy owner has admin credentials on paper (stored securely on-site)
- [ ] Owner shown where the backup folder is (`C:\Pharma-POS-AI\backups\`)
- [ ] Owner shown what to do if the system won't start (call your support number)
- [ ] Support contact recorded in the pharmacy's folder

---

## Ongoing Operations

### Daily (automated)
- Nightly backup runs at 11 PM → `.dump` file in `backups\`

### Upgrades

Run a manual backup first, then:

```cmd
docker compose -f docker-compose.client.yml pull
docker compose -f docker-compose.client.yml up -d
docker exec pharma-pos-backend alembic upgrade head
```

Verify login and one test sale after every upgrade.

### Restore from backup

Always take a fresh backup before restoring, then:

```bat
restore.bat
```

Test login and a full sale workflow after every restore.

### Adding a cashier account

From the admin account → Settings → Users → Create User → set role to `cashier`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| App won't open in browser | Check `docker compose -f docker-compose.client.yml ps` — if `pharma-pos-backend` is not `Up`, run `docker logs pharma-pos-backend --tail 30` |
| Backend `unhealthy` after editing `.env` | `docker compose -f docker-compose.client.yml up -d --force-recreate backend` — plain `docker restart` does not reload env |
| `Authentication failed` / wrong password | Check `backend\.env` — `POSTGRES_PASSWORD` must not contain special characters; no `DATABASE_URL=` override line |
| `relation "users" does not exist` | Run `docker exec pharma-pos-backend alembic upgrade head` then create admin again |
| Alembic `invalid interpolation syntax` | `POSTGRES_PASSWORD` has a special character — change to alphanumeric only, reset PostgreSQL password to match, recreate backend |
| Backup folder is empty | Run `backup.bat` manually and watch for errors — usually a Docker container is not running |
| Other machines can't reach the system | Check firewall rule (Step 13). Also confirm they are on the same LAN — not using mobile data |
| System is slow | Check available RAM: `docker stats` — if backend is consistently above 80% memory, the machine needs more RAM or the Docker memory limit needs increasing |
