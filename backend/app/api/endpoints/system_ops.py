"""
System operations endpoints for local deployment support.
"""
from datetime import datetime, timezone
from pathlib import Path
from io import StringIO
import csv
import json
import os
import platform
import subprocess

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_trigger_backup
from app.core.config import settings
from app.db.base import SessionLocal, engine, get_db
from app.models.activity_log import ActivityLog
from app.models.user import User, UserRole
from app.schemas.system import (
    AuditLogEntry,
    AuditLogListResponse,
    BackupStatus,
    BackupTriggerResult,
    SyncRunResult,
    SyncStatus,
    SystemDiagnostics,
)
from app.services.scheduler import scheduler
from app.services.sync_upload_service import SyncUploadService

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
    db = SessionLocal()
    try:
        sync_status = SyncUploadService.sync_status(db)
    finally:
        db.close()
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
        cloud_sync_enabled=sync_status["enabled"],
        cloud_sync_configured=sync_status["configured"],
        sync_pending_count=sync_status["pending_count"],
        sync_failed_count=sync_status["failed_count"],
        sync_sent_count=sync_status["sent_count"],
        sync_last_sent_at=sync_status["last_sent_at"].isoformat() if sync_status["last_sent_at"] else None,
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


@router.get("/sync-status", response_model=SyncStatus)
def get_sync_status(
    current_user: User = Depends(require_trigger_backup),
):
    db = SessionLocal()
    try:
        status_payload = SyncUploadService.sync_status(db)
        return SyncStatus(
            **{
                **status_payload,
                "last_sent_at": status_payload["last_sent_at"].isoformat()
                if status_payload["last_sent_at"]
                else None,
            }
        )
    finally:
        db.close()


@router.post("/sync-now", response_model=SyncRunResult)
def trigger_sync_now(
    current_user: User = Depends(require_trigger_backup),
):
    db = SessionLocal()
    try:
        return SyncRunResult(**SyncUploadService.upload_pending(db))
    finally:
        db.close()


@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    organization_id: int | None = None,
    branch_id: int | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    user_id: int | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List tenant-scoped audit log entries for admin operational review."""
    _require_admin_user(current_user)
    query = _audit_log_query(
        db,
        current_user=current_user,
        organization_id=organization_id,
        branch_id=branch_id,
        action=action,
        entity_type=entity_type,
        user_id=user_id,
        start_at=start_at,
        end_at=end_at,
    )
    total = query.count()
    entries = (
        query.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return AuditLogListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_audit_log_entry(entry) for entry in entries],
    )


@router.get("/audit-logs/export")
def export_audit_logs_csv(
    organization_id: int | None = None,
    branch_id: int | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    user_id: int | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: int = Query(5000, ge=1, le=20000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Export tenant-scoped audit log entries as CSV for support and review."""
    _require_admin_user(current_user)
    entries = (
        _audit_log_query(
            db,
            current_user=current_user,
            organization_id=organization_id,
            branch_id=branch_id,
            action=action,
            entity_type=entity_type,
            user_id=user_id,
            start_at=start_at,
            end_at=end_at,
        )
        .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
        .limit(limit)
        .all()
    )

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "created_at",
            "organization_id",
            "branch_id",
            "source_device_id",
            "user_id",
            "action",
            "entity_type",
            "entity_id",
            "description",
            "extra_data",
            "ip_address",
        ]
    )
    for entry in entries:
        writer.writerow(
            [
                entry.id,
                entry.created_at.isoformat() if entry.created_at else "",
                entry.organization_id or "",
                entry.branch_id or "",
                entry.source_device_id or "",
                entry.user_id or "",
                entry.action,
                entry.entity_type or "",
                entry.entity_id or "",
                entry.description or "",
                json.dumps(entry.extra_data or {}, sort_keys=True),
                entry.ip_address or "",
            ]
        )

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit-logs.csv"'},
    )


def _require_admin_user(current_user: User) -> None:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


def _audit_log_query(
    db: Session,
    *,
    current_user: User,
    organization_id: int | None,
    branch_id: int | None,
    action: str | None,
    entity_type: str | None,
    user_id: int | None,
    start_at: datetime | None,
    end_at: datetime | None,
):
    query = db.query(ActivityLog)
    effective_organization_id = organization_id
    effective_branch_id = branch_id

    if current_user.organization_id is not None:
        if organization_id is not None and organization_id != current_user.organization_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization access denied")
        effective_organization_id = current_user.organization_id

    if current_user.branch_id is not None:
        if branch_id is not None and branch_id != current_user.branch_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Branch access denied")
        effective_branch_id = current_user.branch_id

    if effective_organization_id is not None:
        query = query.filter(ActivityLog.organization_id == effective_organization_id)
    if effective_branch_id is not None:
        query = query.filter(ActivityLog.branch_id == effective_branch_id)
    if action:
        query = query.filter(ActivityLog.action == action.strip())
    if entity_type:
        query = query.filter(ActivityLog.entity_type == entity_type.strip())
    if user_id is not None:
        query = query.filter(ActivityLog.user_id == user_id)
    if start_at is not None:
        query = query.filter(ActivityLog.created_at >= start_at)
    if end_at is not None:
        query = query.filter(ActivityLog.created_at <= end_at)

    return query


def _audit_log_entry(entry: ActivityLog) -> AuditLogEntry:
    return AuditLogEntry(
        id=entry.id,
        organization_id=entry.organization_id,
        branch_id=entry.branch_id,
        source_device_id=entry.source_device_id,
        user_id=entry.user_id,
        action=entry.action,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        description=entry.description,
        extra_data=entry.extra_data,
        ip_address=entry.ip_address,
        created_at=entry.created_at,
    )
