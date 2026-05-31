# SETUP GUIDE — Online-First City Pharmacy (online_pos)

**Mode:** `online_pos`  
**Use case:** City pharmacy with reliable internet, using a cloud-hosted Supabase database  
**Examples:** Accra, Kumasi, Takoradi city pharmacies  
**Audience:** You (the vendor/installer), not the pharmacy staff

---

## How This Mode Works

In `online_pos` mode:
- The pharmacy's POS writes **directly to the cloud database** (Supabase) in real time
- There is **no local PostgreSQL** — the machine only needs Docker for the backend + frontend containers
- If internet drops temporarily, sales are queued in the browser (IndexedDB) and auto-synced when connectivity returns
- The cloud dashboard, customer retention, follow-up scheduling, and AI manager are all available
- Every pharmacy (organization) is isolated from others by their own `organization_id`

> [!IMPORTANT]
> This mode requires a stable internet connection. It is **not** suitable for pharmacies with chronic power cuts or very unreliable internet. Use `local_pos` for those.

---

## What You Need Before the Site Visit

### 1. Provision the pharmacy in the cloud

On your laptop, run the provisioning script against the cloud Supabase database:

```bash
cd /path/to/pharma-pos-ai/backend

DATABASE_URL="postgresql://postgres:PASSWORD@aws-1-eu-central-2.pooler.supabase.com:6543/postgres" \
  python scripts/provision_client.py
```

Enter when prompted:
- Pharmacy name (e.g. `Accra Central Pharmacy`)
- Branch name (e.g. `Main Branch`)
- Device name (e.g. `POS-001`)

The script will print a block like:

```env
CLOUD_SYNC_ORGANIZATION_ID=42
CLOUD_SYNC_BRANCH_ID=17
CLOUD_SYNC_API_TOKEN=abcdef...
CLOUD_SYNC_DEVICE_UID=pos-001-uuid
```

**Save this block.** You will need it during Step 6 on-site.

### 2. Create an admin account for this pharmacy

Still on your laptop:

```bash
DATABASE_URL="postgresql://..." \
  python scripts/provision_admin.py --organization-id 42
```

Set a strong password. Record it securely — the pharmacy owner needs it for first login.

### 3. Prepare the installation USB / folder

Copy the project release to a USB stick or network share:
```
docker-compose.client.yml
setup-env.bat           (or setup-env.sh on Linux/Mac)
backend/.env.client.example
```

---

## On-Site Installation Steps

### Step 1 — Prepare the Windows machine

Requirements:
- Windows 10 64-bit or newer
- At least 4 GB RAM (8 GB recommended)
- Stable internet (check: browse to `supabase.com` — must load cleanly)
- No VPN that would block outbound HTTPS (port 443)

### Step 2 — Enable WSL 2 and install Docker Desktop

Open PowerShell as Administrator:

```powershell
wsl --install
```

Restart the machine if prompted. Then download and install **Docker Desktop for Windows**:
- Enable WSL 2 backend during install
- Do not enable Kubernetes

Verify both are working:

```cmd
docker --version
docker compose version
```

Both commands must return a version number before continuing.

### Step 3 — Copy application files

Copy the release folder to:

```
C:\Pharma-POS-AI
```

Verify these are present:
- `docker-compose.client.yml`
- `setup-env.bat`
- `backup.bat`
- `restore.bat`
- `backend\.env.client.example`

### Step 4 — Authenticate with GitHub Container Registry

You need a GitHub Personal Access Token (PAT) with `read:packages` scope.  
Generate one at: `https://github.com/settings/tokens` → classic token → tick **read:packages**.

```cmd
docker login ghcr.io -u JohnEvansOkyere -p YOUR_PAT_HERE
```

`Login Succeeded` must appear. Stored on this machine — no need to repeat on upgrades.

### Step 5 — Configure the environment

Open Command Prompt in `C:\Pharma-POS-AI` and run:

```bat
setup-env.bat
```

Enter the pharmacy name and a strong PostgreSQL password (letters and numbers only — no `@`, `!`, `#`, `%`).

After the script finishes, open `backend\.env` and:
1. Set `APP_MODE=online_pos`
2. Set `DATABASE_BACKEND=postgresql` — but the connection string points to **Supabase**, not localhost. Your `DATABASE_URL` should look like:
   ```
   DATABASE_URL=postgresql://postgres.xxxx:PASSWORD@aws-1-eu-central-2.pooler.supabase.com:6543/postgres
   ```
3. Paste the provisioning block from **Preparation Step 1** at the bottom:
   ```env
   CLOUD_SYNC_ORGANIZATION_ID=42
   CLOUD_SYNC_BRANCH_ID=17
   CLOUD_SYNC_API_TOKEN=abcdef...
   CLOUD_SYNC_DEVICE_UID=pos-001-uuid
   ```
4. Set SMS provider (for digital receipts and follow-ups):
   ```env
   SMS_PROVIDER=africas_talking
   SMS_USERNAME=your-at-username
   SMS_API_KEY=your-at-api-key
   SMS_SENDER_ID=PharmaPOS
   ```
5. Set `ENVIRONMENT=production` and `DEBUG=false`

> [!WARNING]
> Do not set `CLOUD_SYNC_ENABLED=true` in `online_pos` mode. The sync outbox is disabled in this mode — data goes directly to the cloud. Setting this flag will do nothing but is confusing.

### Step 6 — Start the services

The `online_pos` mode does **not** need a local database container. Use a trimmed compose file or override:

```cmd
docker compose -f docker-compose.client.yml up -d backend frontend
```

(Only backend and frontend containers — no `db` container needed.)

Wait 60–90 seconds for images to download on first run. Check:

```cmd
docker compose -f docker-compose.client.yml ps
```

`pharma-pos-backend` and `pharma-pos-frontend` must both show `Up`.

### Step 7 — Run database migrations

Migrations run against the Supabase cloud database:

```cmd
docker exec pharma-pos-backend alembic upgrade head
```

This is safe to run on every install and every upgrade.

### Step 8 — Verify the application

Open a browser and go to:
```
http://localhost:8080
```

Log in with the admin account created in **Preparation Step 2**.

Run this verification checklist:

- [ ] Login works
- [ ] Cloud dashboard loads (admin/manager should land here by default)
- [ ] Products page is accessible
- [ ] Add one test product
- [ ] POS page: complete a test sale (cash payment)
- [ ] The sale appears in Sales list
- [ ] Simulate offline: disconnect WiFi → attempt a sale → it shows "Queued" toast with a TMP invoice number
- [ ] Reconnect WiFi → the Offline Queue page (`/offline-queue`) shows the pending sale → click Flush → sale syncs

### Step 9 — Create desktop shortcut

```powershell
$s = "[InternetShortcut]`r`nURL=http://localhost:8080`r`nIconFile=C:\Pharma-POS-AI\PHARMACY.ico`r`nIconIndex=0"
$s | Out-File "$env:PUBLIC\Desktop\Pharma POS.url" -Encoding ASCII
```

### Step 10 — Set containers to auto-start

```cmd
docker update --restart always pharma-pos-backend pharma-pos-frontend
```

The system will now start automatically when Windows boots — no manual steps needed after a reboot.

---

## Handover Checklist

Do not hand over until every item is ticked:

- [ ] Admin login works
- [ ] Cashier login works (create a cashier account if not done)
- [ ] POS sale completes end to end
- [ ] Cloud dashboard shows sale data
- [ ] Customer registration works (Customers page)
- [ ] Offline queue demo: queue a sale, flush it, confirm it synced
- [ ] Machine rebooted — system came back up automatically
- [ ] Pharmacy owner has their admin credentials written on paper (stored securely)
- [ ] Support contact recorded

---

## Ongoing Operations

### Upgrade

1. Pull new images:
   ```cmd
   docker compose -f docker-compose.client.yml pull
   ```
2. Restart:
   ```cmd
   docker compose -f docker-compose.client.yml up -d backend frontend
   ```
3. Run migrations:
   ```cmd
   docker exec pharma-pos-backend alembic upgrade head
   ```
4. Verify login and POS

### Monitoring

Since data is in the cloud, you can monitor from your laptop:
- Log into the Supabase dashboard to check table counts
- Check `docker logs pharma-pos-backend --tail 50` for any backend errors

### Customer Data & SMS

To activate Africa's Talking SMS for digital receipts:
1. Get the production API key from the AT dashboard
2. Update `.env`: `SMS_PROVIDER=africas_taking`, `SMS_API_KEY=...`
3. Recreate the backend container: `docker compose -f docker-compose.client.yml up -d backend`

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Backend won't start | Check `docker logs pharma-pos-backend` — usually a bad `DATABASE_URL` or Supabase unreachable |
| `relation "users" does not exist` | Run `docker exec pharma-pos-backend alembic upgrade head` |
| Offline sale queued but won't flush | Check internet is up. Go to `/offline-queue` and click "Flush Now". Check backend logs for the specific error |
| Cloud dashboard shows no data | Confirm `CLOUD_SYNC_ORGANIZATION_ID` is set correctly — it must match the org created during provisioning |
| SMS not sending | Set `SMS_PROVIDER=africas_talking` and confirm `SMS_API_KEY` is the **production** key, not sandbox |
| Backend `unhealthy` after editing `.env` | `docker compose -f docker-compose.client.yml up -d --force-recreate backend` — plain `docker restart` does not reload env |
