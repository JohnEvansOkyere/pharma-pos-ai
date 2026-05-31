# Windows Local Deployment Runbook

Each pharmacy gets its own machine, database, secrets, and backup set.

---

## Part 1 — Before the Site Visit (Your Machine)

### Step 1. Provision Cloud Sync (skip if offline-only install)

Run this on your laptop to register the pharmacy in Supabase and generate its credentials:

```bash
cd /path/to/pharma-pos-ai/backend
DATABASE_URL="postgresql://postgres:PASSWORD@aws-1-eu-central-2.pooler.supabase.com:6543/postgres" \
  python scripts/provision_client.py
```

Enter the pharmacy name, branch name, and device name when prompted. The script prints a block like:

```env
CLOUD_SYNC_ENABLED=true
CLOUD_SYNC_INGEST_URL=https://pharma-pos-ai.onrender.com/api/sync/ingest
CLOUD_SYNC_API_TOKEN=...
CLOUD_SYNC_DEVICE_UID=...
CLOUD_SYNC_ORGANIZATION_ID=...
CLOUD_SYNC_BRANCH_ID=...
```

Save this block. You will paste it into `backend\.env` during Step 6.

---

## Part 2 — On-Site Installation

### Step 2. Enable WSL 2

Open PowerShell as Administrator:

```powershell
wsl --install
```

Restart if prompted.

### Step 3. Install Docker Desktop

Download and install Docker Desktop for Windows. During installation:
- Enable WSL 2 backend
- Do not enable Kubernetes

After installation, start Docker Desktop and wait until the system tray icon shows **Docker Desktop is running**.

Verify:

```cmd
docker --version
docker compose version
```

Both must succeed before continuing.

### Step 4. Copy Application Files

Copy the project to:

```
C:\Pharma-POS-AI
```

Confirm these files are present:
- `docker-compose.client.yml`
- `setup-env.bat`
- `backup.bat`
- `restore.bat`
- `install_backup_task.bat`
- `backend\.env.client.example`

### Step 5. Authenticate With GitHub Container Registry

You need a GitHub Personal Access Token (PAT) with `read:packages` scope. Generate one at:
`https://github.com/settings/tokens` → Generate new token (classic) → tick **read:packages**.

```cmd
docker login ghcr.io -u JohnEvansOkyere -p YOUR_PAT_HERE
```

You should see `Login Succeeded`. This is stored on the machine — no need to repeat on future upgrades unless the token expires.

### Step 6. Configure Environment

Open a Command Prompt in `C:\Pharma-POS-AI` and run:

```bat
setup-env.bat
```

Enter the pharmacy name and PostgreSQL password when prompted.

After the script finishes, open `backend\.env` and confirm:
- `POSTGRES_PASSWORD` is the value you entered — not empty
- `SECRET_KEY` is a long generated string — not a placeholder
- `ENVIRONMENT=production`
- No line starting with `DATABASE_URL=` — delete it if present

**Password rule:** Use letters and numbers only in `POSTGRES_PASSWORD`. No `@`, `!`, `#`, `$`, `%`. Special characters break URL parsing and Alembic.

If this is a cloud sync install, paste the block from Step 1 at the bottom of `backend\.env`.

### Step 7. Start Services

```cmd
docker compose -f docker-compose.client.yml up -d
```

Wait 1–2 minutes for images to download on the first run. Then check:

```cmd
docker compose -f docker-compose.client.yml ps
```

All three services (`pharma-pos-db`, `pharma-pos-backend`, `pharma-pos-frontend`) must show `Up` or `healthy`. If the backend shows `unhealthy`, wait 60 seconds and check again.

### Step 8. Run Database Migrations

```cmd
docker exec pharma-pos-backend alembic upgrade head
```

Safe to run on every install and every upgrade.

### Step 9. Create the Admin Account

```cmd
docker exec -it pharma-pos-backend python scripts/provision_admin.py
```

Enter username, email, full name, and password. This is the pharmacy owner's account — make it strong.

### Step 10. Verify the Application

Open a browser and go to:

```
http://localhost:8080
```

Log in with the admin account. Confirm:
- Dashboard loads
- Products page is accessible
- POS page opens and a test sale completes

### Step 11. Create Desktop Shortcut

Run in PowerShell from `C:\Pharma-POS-AI`:

```powershell
$s = "[InternetShortcut]`r`nURL=http://localhost:8080`r`nIconFile=C:\Pharma-POS-AI\PHARMACY.ico`r`nIconIndex=0"
$s | Out-File "$env:PUBLIC\Desktop\Pharma POS.url" -Encoding ASCII
```

### Step 12. Open Firewall (only if other machines need access)

If pharmacy staff will access the system from other computers on the same network, open port 8080 in Windows Defender Firewall. If only one workstation is used, skip this step.

### Step 13. Install Backup Schedule

Open a Command Prompt in `C:\Pharma-POS-AI` as Administrator:

```bat
install_backup_task.bat
```

This installs the daily local database backup for 11:00 PM, after normal pharmacy closing hours.

Run a manual backup to confirm it works:

```bat
backup.bat
```

A `.dump` file must appear in the `backups\` folder before you proceed.

---

## Part 3 — Handover Checklist

Do not hand over until every item below is verified:

- [ ] Admin login works
- [ ] Cashier login works
- [ ] POS sale completes end to end
- [ ] Product add and stock receipt work
- [ ] Sale void or refund tested
- [ ] Closeout summary reviewed
- [ ] Desktop shortcut opens the app
- [ ] Manual backup ran and `.dump` file exists
- [ ] Machine rebooted and system came back up without manual steps
- [ ] Backup folder location shown to client
- [ ] Support contact recorded

---

## Part 4 — Ongoing Operations

### Upgrade

1. Run a manual backup first
2. Pull new images:
   ```cmd
   docker compose -f docker-compose.client.yml pull
   ```
3. Restart with new images:
   ```cmd
   docker compose -f docker-compose.client.yml up -d
   ```
4. Run migrations:
   ```cmd
   docker exec pharma-pos-backend alembic upgrade head
   ```
5. Verify login, products, and POS

### Backup

Run manually at any time:

```bat
backup.bat
```

Or confirm the scheduled task is active:

```cmd
schtasks /query /tn "PharmaBackup"
```

### Restore

Always create a fresh backup before restoring. Then:

```bat
restore.bat
```

Test login and a sample workflow after every restore.

---

## Part 5 — Quick Fixes

| Problem | Fix |
|---|---|
| Backend `unhealthy` after editing `.env` | `docker compose -f docker-compose.client.yml up -d --force-recreate backend` — `docker restart` does not reload env |
| Authentication failed — wrong password | `docker exec pharma-pos-backend env \| findstr POSTGRES` — check for a `DATABASE_URL=` line overriding the password; delete it from `.env` then recreate backend |
| `relation "users" does not exist` | Run `docker exec pharma-pos-backend alembic upgrade head` then provision admin again |
| Alembic `invalid interpolation syntax` | `POSTGRES_PASSWORD` contains a special character — change to alphanumeric only, reset DB password to match, recreate backend |
| `docker login` succeeds but image pull fails | Image name in `docker-compose.client.yml` must be lowercase and match the GitHub username exactly |
| Frontend shows `unhealthy` | Ignore — the nginx container serves the app correctly; open `http://localhost:8080` to confirm |
