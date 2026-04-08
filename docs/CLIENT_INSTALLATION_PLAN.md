# Client Installation Plan

## Goal

Ship a repeatable, offline-first Windows installation for Ghanaian pharmacies:
- PostgreSQL runs locally
- backend service runs automatically on startup
- frontend is launched via shortcut pointing to the local backend
- backups and restores are available from the installed folder

## Install Steps

1. **Prepare Windows machine**
   - Install PostgreSQL 13+ for Windows
   - Ensure `pg_dump`/`psql` are in `PATH`
   - Create Windows user `pharmapos` (optional) with admin rights

2. **Generate secrets**
   - Run `openssl rand -hex 32` to produce `SECRET_KEY`
   - Pick a strong password for `POSTGRES_PASSWORD`

3. **Run installer**
   - Run `Pharma-POS-AI-Setup.exe` (created from `installer.iss`)
   - Installer copies backend/fronted, backup & helper scripts, and creates shortcuts
   - During install the included `setup-env.bat` should populate `.env` with the secrets and PostgreSQL connection settings

4. **Initial database setup**
   - Inside the installed directory run `backend\setup-env.bat` (if not already run)
   - Use `scripts/init_db.sh` from the root to run migrations and optionally seed data:
     ```
     cd "%ProgramFiles%\Pharma-POS-AI"
     bash scripts/init_db.sh
     ```

5. **Configure Windows service**
   - Use [`sc.exe`](https://learn.microsoft.com/windows-server/administration/windows-commands/sc-create) or NSSM to install `uvicorn` or the included `start.bat` as a service
   - Point the service to `backend\venv\Scripts\python.exe -m app.main`
   - Set service to restart on failure and start automatically

6. **Create frontend shortcut**
   - Add a desktop shortcut to `start.bat` or the frontend `index.html`
   - Document the local URLs (`http://localhost:8000` for API, `http://localhost:8080` for UI)

## Backup / Restore in the Installer

- Installer already copies `backup.bat` and the new `restore.bat` for technicians
- Add documentation (see `docs/BACKUP_RESTORE_GUIDE.md`) to the installed folder
- During installation consider wiring a scheduled task to run `backup.bat` nightly

## Support Checklist

| Item | Verified? |
| --- | --- |
| PostgreSQL service started | ☐ |
| Backend service installed & running | ☐ |
| Frontend shortcut on desktop | ☐ |
| Nightly backup scheduled | ☐ |
| Restore procedure documented | ☐ |
| `start.bat`/`stop.bat` accessible | ☐ |

## Next Dev Tasks

1. Build a PowerShell helper to register `uvicorn` as a service during install.
2. Update `installer.iss` post-install message to reference the local docs and backup scripts.
3. Create a health-check page (maybe `http://localhost:8000/health`) that the service manager can query.
