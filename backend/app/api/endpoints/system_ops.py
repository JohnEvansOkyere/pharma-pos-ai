"""
System operations endpoints for local deployment support.
"""
from datetime import datetime, timezone
from pathlib import Path
import os
import platform
import subprocess

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text

from app.api.dependencies import require_trigger_backup
from app.core.config import settings
from app.db.base import engine
from app.models.user import User
from app.schemas.system import BackupStatus, BackupTriggerResult, SystemDiagnostics
from app.services.scheduler import scheduler

router = APIRouter(prefix="/system", tags=["System"])

ROOT_DIR = Path(__file__).resolve().parents[4]
BACKUP_DIR = ROOT_DIR / "backups"
BACKUP_STATUS_FILE = BACKUP_DIR / "latest_backup.txt"
WINDOWS_BACKUP_SCRIPT = ROOT_DIR / "backup.bat"
WINDOWS_SCHEDULE_HELPER = ROOT_DIR / "install_backup_task.bat"
LINUX_BACKUP_SCRIPT = ROOT_DIR / "scripts" / "backup_postgres.sh"
LINUX_SCHEDULE_HELPER = ROOT_DIR / "scripts" / "install_backup_cron.sh"
FRONTEND_DIST_DIR = ROOT_DIR / "frontend" / "dist"


def _get_retention_days() -> int:
    raw_value = os.getenv("BACKUP_RETENTION_DAYS", "30")
    try:
        return max(1, int(raw_value))
    except ValueError:
        return 30


def _get_latest_backup_path() -> Path | None:
    if BACKUP_STATUS_FILE.exists():
        latest_path = BACKUP_STATUS_FILE.read_text(encoding="utf-8").strip()
        if latest_path:
            candidate = Path(latest_path)
            if not candidate.is_absolute():
                candidate = ROOT_DIR / latest_path
            return candidate

    backup_files = sorted(BACKUP_DIR.glob("*.dump"), key=lambda path: path.stat().st_mtime, reverse=True)
    return backup_files[0] if backup_files else None


def _build_backup_status() -> BackupStatus:
    latest_backup = _get_latest_backup_path()
    latest_exists = bool(latest_backup and latest_backup.exists())

    latest_backup_time = None
    latest_backup_size = None
    latest_backup_age_hours = None
    backup_is_recent = False

    if latest_exists and latest_backup is not None:
        modified_at = datetime.fromtimestamp(latest_backup.stat().st_mtime, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        latest_backup_age_hours = round((now - modified_at).total_seconds() / 3600, 2)
        latest_backup_time = modified_at.astimezone().isoformat(timespec="seconds")
        latest_backup_size = latest_backup.stat().st_size
        backup_is_recent = latest_backup_age_hours <= 26

    is_windows = platform.system().lower().startswith("win")

    return BackupStatus(
        platform=platform.system(),
        backup_dir=str(BACKUP_DIR),
        latest_backup_path=str(latest_backup) if latest_backup else None,
        latest_backup_exists=latest_exists,
        latest_backup_time=latest_backup_time,
        latest_backup_size_bytes=latest_backup_size,
        latest_backup_age_hours=latest_backup_age_hours,
        backup_is_recent=backup_is_recent,
        retention_days=_get_retention_days(),
        trigger_available=(WINDOWS_BACKUP_SCRIPT if is_windows else LINUX_BACKUP_SCRIPT).exists(),
        schedule_helper_available=(WINDOWS_SCHEDULE_HELPER if is_windows else LINUX_SCHEDULE_HELPER).exists(),
    )


def _run_backup() -> None:
    is_windows = platform.system().lower().startswith("win")

    if is_windows:
        if not WINDOWS_BACKUP_SCRIPT.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Windows backup script is not available",
            )
        env = os.environ.copy()
        env["PHARMA_BACKUP_NONINTERACTIVE"] = "1"
        result = subprocess.run(
            ["cmd.exe", "/c", str(WINDOWS_BACKUP_SCRIPT)],
            cwd=str(ROOT_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
    else:
        if not LINUX_BACKUP_SCRIPT.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Linux backup script is not available",
            )
        result = subprocess.run(
            ["bash", str(LINUX_BACKUP_SCRIPT)],
            cwd=str(ROOT_DIR),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=300,
        )

    if result.returncode != 0:
        error_output = (result.stderr or result.stdout or "").strip()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_output or "Backup failed",
        )


def _database_connected() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _build_system_diagnostics() -> SystemDiagnostics:
    backup = _build_backup_status()
    return SystemDiagnostics(
        platform=platform.system(),
        app_version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        database_backend=settings.DATABASE_BACKEND,
        database_connected=_database_connected(),
        scheduler_enabled=settings.ENABLE_BACKGROUND_SCHEDULER,
        scheduler_running=bool(scheduler.scheduler.running),
        scheduler_job_count=len(scheduler.scheduler.get_jobs()),
        backup_dir=backup.backup_dir,
        latest_backup_exists=backup.latest_backup_exists,
        latest_backup_time=backup.latest_backup_time,
        backup_is_recent=backup.backup_is_recent,
        frontend_dist_available=FRONTEND_DIST_DIR.exists(),
        windows_backup_task_helper_available=WINDOWS_SCHEDULE_HELPER.exists(),
        linux_backup_cron_helper_available=LINUX_SCHEDULE_HELPER.exists(),
    )


@router.get("/backup-status", response_model=BackupStatus)
def get_backup_status(
    current_user: User = Depends(require_trigger_backup),
):
    return _build_backup_status()


@router.post("/backup-now", response_model=BackupTriggerResult)
def trigger_backup(
    current_user: User = Depends(require_trigger_backup),
):
    _run_backup()
    return BackupTriggerResult(
        success=True,
        message="Backup completed successfully",
        backup=_build_backup_status(),
    )


@router.get("/diagnostics", response_model=SystemDiagnostics)
def get_system_diagnostics(
    current_user: User = Depends(require_trigger_backup),
):
    return _build_system_diagnostics()
