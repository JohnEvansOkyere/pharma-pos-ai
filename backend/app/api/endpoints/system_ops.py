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
import shutil
import subprocess

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_trigger_backup
from app.core.config import settings
from app.db.base import SessionLocal, engine, get_db
from app.models.activity_log import ActivityLog
from app.models.restore_drill import RestoreDrill
from app.models.user import User, UserRole
from app.schemas.system import (
    AuditIntegrityStatus,
    AuditLogEntry,
    AuditLogListResponse,
    BackupStatus,
    BackupTriggerResult,
    CloudSyncNowResult,
    CloudSnapshotEnqueueResult,
    RestoreDrillCreate,
    RestoreDrillRecord,
    RestoreDrillStatus,
    SystemHeartbeatEnqueueResult,
    SyncRunResult,
    SyncStatus,
    SystemDiagnostics,
)
from app.services.audit_service import AuditService
from app.services.full_snapshot_sync_service import FullSnapshotSyncService
from app.services.scheduler import scheduler
from app.services.system_heartbeat_service import SystemHeartbeatService
from app.services.sync_upload_service import SyncUploadService

router = APIRouter(prefix="/system", tags=["System"])


def _project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "backup.bat").exists() or (parent / "docker-compose.yml").exists():
            return parent
        if (parent / "app").exists() and (parent / "alembic").exists():
            return parent
    return current.parents[3]


ROOT_DIR = _project_root()
BACKUP_DIR = Path(os.getenv("BACKUP_DIR") or (ROOT_DIR / "backups"))
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


def _get_restore_drill_max_age_days() -> int:
    raw_value = os.getenv("RESTORE_DRILL_MAX_AGE_DAYS", "90")
    try:
        return max(1, int(raw_value))
    except ValueError:
        return 90


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
            _run_pg_dump_backup()
            return
        command = ["cmd.exe", "/c", str(WINDOWS_BACKUP_SCRIPT)]
        cwd = ROOT_DIR
    else:
        if not LINUX_BACKUP_SCRIPT.exists():
            _run_pg_dump_backup()
            return
        command = ["bash", str(LINUX_BACKUP_SCRIPT)]
        cwd = ROOT_DIR

    env = os.environ.copy()
    env["PHARMA_BACKUP_NONINTERACTIVE"] = "1"
    result = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
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


def _run_pg_dump_backup() -> None:
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="pg_dump is not available in the backend environment",
        )

    postgres_password = os.getenv("POSTGRES_PASSWORD") or ""
    if not postgres_password:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="POSTGRES_PASSWORD is not configured",
        )

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    postgres_db = os.getenv("POSTGRES_DB") or "pharma_pos"
    backup_file = BACKUP_DIR / f"{postgres_db}_backup_{timestamp}.dump"

    env = os.environ.copy()
    env["PGPASSWORD"] = postgres_password
    result = subprocess.run(
        [
            pg_dump,
            "-h",
            os.getenv("POSTGRES_HOST") or "localhost",
            "-p",
            str(os.getenv("POSTGRES_PORT") or "5432"),
            "-U",
            os.getenv("POSTGRES_USER") or "pharma_user",
            "-d",
            postgres_db,
            "-F",
            "c",
            "-f",
            str(backup_file),
        ],
        cwd=str(ROOT_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        backup_file.unlink(missing_ok=True)
        error_output = (result.stderr or result.stdout or "").strip()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_output or "Backup failed",
        )

    BACKUP_STATUS_FILE.write_text(str(backup_file), encoding="utf-8")
    retention_days = _get_retention_days()
    cutoff_seconds = retention_days * 24 * 60 * 60
    now = datetime.now(timezone.utc).timestamp()
    for candidate in BACKUP_DIR.glob(f"{postgres_db}_backup_*.dump"):
        if now - candidate.stat().st_mtime > cutoff_seconds:
            candidate.unlink(missing_ok=True)


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


@router.get("/restore-drill-status", response_model=RestoreDrillStatus)
def get_restore_drill_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_trigger_backup),
):
    return _build_restore_drill_status(db)


@router.post("/restore-drills", response_model=RestoreDrillRecord, status_code=status.HTTP_201_CREATED)
def record_restore_drill(
    payload: RestoreDrillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_trigger_backup),
):
    status_value = payload.status.strip().lower()
    if status_value not in {"passed", "failed"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Restore drill status must be passed or failed",
        )

    restore_target = payload.restore_target.strip()
    if not restore_target:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Restore target is required",
        )

    backup = _build_backup_status()
    backup_path = payload.backup_path.strip() if payload.backup_path else backup.latest_backup_path
    if not backup_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A backup path is required because no latest backup is available",
        )

    drill = RestoreDrill(
        status=status_value,
        backup_path=backup_path,
        backup_created_at=datetime.fromisoformat(backup.latest_backup_time) if backup.latest_backup_time else None,
        backup_size_bytes=backup.latest_backup_size_bytes,
        restore_target=restore_target,
        notes=payload.notes,
        verification_summary=payload.verification_summary or {},
        tested_by_user_id=current_user.id,
        tested_at=payload.tested_at or datetime.now(timezone.utc),
    )
    db.add(drill)
    db.flush()
    AuditService.log(
        db,
        action="record_restore_drill",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        branch_id=current_user.branch_id,
        entity_type="restore_drill",
        entity_id=drill.id,
        description=f"Recorded restore drill as {status_value}",
        extra_data={
            "status": status_value,
            "backup_path": backup_path,
            "restore_target": restore_target,
            "latest_backup_exists": backup.latest_backup_exists,
            "backup_is_recent": backup.backup_is_recent,
        },
    )
    db.commit()
    db.refresh(drill)
    return _restore_drill_record(drill)


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


@router.post("/cloud-sync-now", response_model=CloudSyncNowResult)
def trigger_cloud_sync_now(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_trigger_backup),
):
    """Enqueue the current local catalog snapshot and upload pending events immediately."""
    try:
        snapshot_data = FullSnapshotSyncService.enqueue_catalog_snapshot(
            db,
            include_inactive=include_inactive,
        )
        AuditService.log(
            db,
            action="manual_cloud_sync_snapshot",
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            branch_id=current_user.branch_id,
            entity_type="sync_event",
            entity_id=None,
            description="Manual cloud sync snapshot enqueued from Settings",
            extra_data=snapshot_data,
        )
        db.commit()
        upload_data = SyncUploadService.upload_pending(db)
        return CloudSyncNowResult(
            success=upload_data["failed"] == 0,
            snapshot=CloudSnapshotEnqueueResult(
                success=True,
                message="Full catalog snapshot enqueued for cloud sync",
                **snapshot_data,
            ),
            upload=SyncRunResult(**upload_data),
            message="Cloud sync run complete",
        )
    except Exception:
        db.rollback()
        raise


@router.post("/enqueue-cloud-snapshot", response_model=CloudSnapshotEnqueueResult)
def enqueue_cloud_snapshot(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_trigger_backup),
):
    """Enqueue a full product and batch snapshot for first-time cloud hydration."""
    try:
        result = FullSnapshotSyncService.enqueue_catalog_snapshot(
            db,
            include_inactive=include_inactive,
        )
        AuditService.log(
            db,
            action="enqueue_cloud_snapshot",
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            branch_id=current_user.branch_id,
            entity_type="sync_event",
            entity_id=None,
            description="Enqueued full catalog snapshot for cloud sync",
            extra_data=result,
        )
        db.commit()
        return CloudSnapshotEnqueueResult(
            success=True,
            message="Full catalog snapshot enqueued for cloud sync",
            **result,
        )
    except Exception:
        db.rollback()
        raise


@router.post("/enqueue-heartbeat", response_model=SystemHeartbeatEnqueueResult)
def enqueue_system_heartbeat(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_trigger_backup),
):
    """Enqueue local installation health telemetry for cloud sync."""
    try:
        event = SystemHeartbeatService.enqueue_heartbeat(
            db,
            scheduler_running=bool(scheduler.scheduler.running),
            scheduler_job_count=len(scheduler.scheduler.get_jobs()),
        )
        db.commit()
        return SystemHeartbeatEnqueueResult(
            success=True,
            event_id=event.event_id,
            local_sequence_number=event.local_sequence_number,
            readiness_status=event.payload.get("readiness_status", "unknown"),
            sync_pending_count=int(event.payload.get("sync_pending_count") or 0),
            sync_failed_count=int(event.payload.get("sync_failed_count") or 0),
            oldest_unsent_event_age_minutes=event.payload.get("oldest_unsent_event_age_minutes"),
            message="System heartbeat enqueued for cloud sync",
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise


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
            "hash_version",
            "previous_hash",
            "current_hash",
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
                entry.hash_version or "",
                entry.previous_hash or "",
                entry.current_hash or "",
            ]
        )

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit-logs.csv"'},
    )


@router.get("/audit-integrity", response_model=AuditIntegrityStatus)
def get_audit_integrity(
    organization_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Verify tamper-evident hash chains for audit logs."""
    _require_admin_user(current_user)
    effective_organization_id = organization_id
    if current_user.organization_id is not None:
        if organization_id is not None and organization_id != current_user.organization_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization access denied")
        effective_organization_id = current_user.organization_id

    return AuditIntegrityStatus(
        **AuditService.verify_integrity(
            db,
            organization_id=effective_organization_id,
        )
    )


def _build_restore_drill_status(db: Session) -> RestoreDrillStatus:
    backup = _build_backup_status()
    max_age_days = _get_restore_drill_max_age_days()
    last_drill = db.query(RestoreDrill).order_by(RestoreDrill.tested_at.desc(), RestoreDrill.id.desc()).first()
    last_success = (
        db.query(RestoreDrill)
        .filter(RestoreDrill.status == "passed")
        .order_by(RestoreDrill.tested_at.desc(), RestoreDrill.id.desc())
        .first()
    )
    now = datetime.now(timezone.utc)
    successful_drill_recent = False
    if last_success is not None:
        tested_at = last_success.tested_at
        if tested_at.tzinfo is None:
            tested_at = tested_at.replace(tzinfo=timezone.utc)
        successful_drill_recent = (now - tested_at).days <= max_age_days

    latest_backup_tested = bool(
        last_success
        and backup.latest_backup_path
        and last_success.backup_path == backup.latest_backup_path
    )
    recovery_ready = bool(
        backup.latest_backup_exists
        and backup.backup_is_recent
        and successful_drill_recent
    )
    checklist = [
        {
            "key": "backup_exists",
            "label": "Latest backup exists",
            "status": "passed" if backup.latest_backup_exists else "failed",
            "message": backup.latest_backup_path or "No backup file found",
        },
        {
            "key": "backup_recent",
            "label": "Latest backup is recent",
            "status": "passed" if backup.backup_is_recent else "failed",
            "message": (
                f"Backup age is {backup.latest_backup_age_hours} hour(s)"
                if backup.latest_backup_age_hours is not None
                else "Backup age is unavailable"
            ),
        },
        {
            "key": "restore_drill_recent",
            "label": "Restore drill completed recently",
            "status": "passed" if successful_drill_recent else "failed",
            "message": (
                f"Last passed drill was {last_success.tested_at.isoformat()}"
                if last_success
                else "No passed restore drill recorded"
            ),
        },
        {
            "key": "latest_backup_tested",
            "label": "Latest backup was tested",
            "status": "passed" if latest_backup_tested else "warning",
            "message": (
                "Latest backup path matches the last passed drill"
                if latest_backup_tested
                else "Last passed drill may have tested an older backup"
            ),
        },
    ]
    return RestoreDrillStatus(
        backup=backup,
        last_drill=_restore_drill_record(last_drill) if last_drill else None,
        recovery_ready=recovery_ready,
        latest_backup_tested=latest_backup_tested,
        drill_max_age_days=max_age_days,
        checklist=checklist,
    )


def _restore_drill_record(drill: RestoreDrill) -> RestoreDrillRecord:
    return RestoreDrillRecord(
        id=drill.id,
        status=drill.status,
        backup_path=drill.backup_path,
        backup_created_at=drill.backup_created_at,
        backup_size_bytes=drill.backup_size_bytes,
        restore_target=drill.restore_target,
        notes=drill.notes,
        verification_summary=drill.verification_summary or {},
        tested_by_user_id=drill.tested_by_user_id,
        tested_at=drill.tested_at,
        created_at=drill.created_at,
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
        hash_version=entry.hash_version,
        previous_hash=entry.previous_hash,
        current_hash=entry.current_hash,
        created_at=entry.created_at,
    )
