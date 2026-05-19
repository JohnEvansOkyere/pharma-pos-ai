"""
Build and enqueue local installation heartbeat telemetry for cloud sync.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os
import platform
import shutil

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import engine
from app.models.restore_drill import RestoreDrill
from app.models.sync_event import SyncEvent, SyncEventStatus, SyncEventType
from app.models.tenancy import Device
from app.services.sync_outbox_service import SyncOutboxService
from app.services.sync_upload_service import SyncUploadService

ROOT_DIR = Path(__file__).resolve().parents[3]
BACKUP_DIR = ROOT_DIR / "backups"
BACKUP_STATUS_FILE = BACKUP_DIR / "latest_backup.txt"
PROCESS_STARTED_AT = datetime.now(timezone.utc)


class SystemHeartbeatService:
    """Collect local health facts and enqueue them through the normal outbox."""

    @staticmethod
    def _database_connected(db: Session | None = None) -> bool:
        try:
            if db is not None:
                db.execute(text("SELECT 1"))
            else:
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    @staticmethod
    def _latest_backup() -> tuple[str | None, int | None, float | None, bool]:
        latest_backup = None
        if BACKUP_STATUS_FILE.exists():
            latest_path = BACKUP_STATUS_FILE.read_text(encoding="utf-8").strip()
            if latest_path:
                latest_backup = Path(latest_path)
                if not latest_backup.is_absolute():
                    latest_backup = ROOT_DIR / latest_path

        if latest_backup is None:
            backup_files = sorted(
                BACKUP_DIR.glob("*.dump"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            latest_backup = backup_files[0] if backup_files else None

        if latest_backup is None or not latest_backup.exists():
            return None, None, None, False

        modified_at = datetime.fromtimestamp(latest_backup.stat().st_mtime, tz=timezone.utc)
        age_hours = round((datetime.now(timezone.utc) - modified_at).total_seconds() / 3600, 2)
        return modified_at.isoformat(), latest_backup.stat().st_size, age_hours, age_hours <= 26

    @staticmethod
    def _restore_status(db: Session) -> tuple[bool, str | None]:
        max_age_days = max(1, int(os.getenv("RESTORE_DRILL_MAX_AGE_DAYS", "90") or 90))
        last_success = (
            db.query(RestoreDrill)
            .filter(RestoreDrill.status == "passed")
            .order_by(RestoreDrill.tested_at.desc(), RestoreDrill.id.desc())
            .first()
        )
        if last_success is None:
            return False, None

        tested_at = last_success.tested_at
        if tested_at.tzinfo is None:
            tested_at = tested_at.replace(tzinfo=timezone.utc)
        is_recent = (datetime.now(timezone.utc) - tested_at).days <= max_age_days
        return is_recent, tested_at.isoformat()

    @staticmethod
    def _oldest_unsent_event_age_minutes(db: Session) -> int | None:
        event = (
            db.query(SyncEvent)
            .filter(SyncEvent.status.in_([SyncEventStatus.PENDING, SyncEventStatus.FAILED]))
            .order_by(SyncEvent.created_at.asc(), SyncEvent.id.asc())
            .first()
        )
        if event is None or event.created_at is None:
            return None
        created_at = event.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - created_at).total_seconds() // 60))

    @staticmethod
    def _readiness_status(payload: dict) -> str:
        if not payload["database_connected"]:
            return "critical"
        if payload["scheduler_enabled"] and not payload["scheduler_running"]:
            return "critical"
        if payload["sync_failed_count"] > 0:
            return "warning"
        if payload.get("oldest_unsent_event_age_minutes") and payload["oldest_unsent_event_age_minutes"] > 60:
            return "warning"
        if not payload["backup_is_recent"] or not payload["restore_recovery_ready"]:
            return "warning"
        return "ready"

    @staticmethod
    def build_payload(
        db: Session,
        *,
        scheduler_running: bool = False,
        scheduler_job_count: int = 0,
    ) -> dict:
        sync_status = SyncUploadService.sync_status(db)
        latest_backup_time, latest_backup_size, latest_backup_age_hours, backup_is_recent = (
            SystemHeartbeatService._latest_backup()
        )
        restore_recovery_ready, last_restore_drill_at = SystemHeartbeatService._restore_status(db)
        disk_usage = shutil.disk_usage(str(ROOT_DIR))
        server_time = datetime.now(timezone.utc)

        payload = {
            "server_time": server_time.isoformat(),
            "platform": platform.system(),
            "app_version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "database_backend": settings.DATABASE_BACKEND,
            "database_connected": SystemHeartbeatService._database_connected(db),
            "scheduler_enabled": settings.ENABLE_BACKGROUND_SCHEDULER,
            "scheduler_running": scheduler_running,
            "scheduler_job_count": scheduler_job_count,
            "cloud_sync_enabled": sync_status["enabled"],
            "cloud_sync_configured": sync_status["configured"],
            "sync_pending_count": sync_status["pending_count"],
            "sync_failed_count": sync_status["failed_count"],
            "sync_sent_count": sync_status["sent_count"],
            "sync_last_sent_at": (
                sync_status["last_sent_at"].isoformat()
                if sync_status["last_sent_at"]
                else None
            ),
            "oldest_unsent_event_age_minutes": SystemHeartbeatService._oldest_unsent_event_age_minutes(db),
            "latest_backup_time": latest_backup_time,
            "latest_backup_size_bytes": latest_backup_size,
            "latest_backup_age_hours": latest_backup_age_hours,
            "backup_is_recent": backup_is_recent,
            "restore_recovery_ready": restore_recovery_ready,
            "last_restore_drill_at": last_restore_drill_at,
            "free_disk_bytes": disk_usage.free,
            "total_disk_bytes": disk_usage.total,
            "uptime_seconds": int((server_time - PROCESS_STARTED_AT).total_seconds()),
        }
        payload["readiness_status"] = SystemHeartbeatService._readiness_status(payload)
        return payload

    @staticmethod
    def enqueue_heartbeat(
        db: Session,
        *,
        scheduler_running: bool = False,
        scheduler_job_count: int = 0,
    ) -> SyncEvent:
        organization_id = settings.CLOUD_SYNC_ORGANIZATION_ID
        branch_id = settings.CLOUD_SYNC_BRANCH_ID
        device_uid = settings.CLOUD_SYNC_DEVICE_UID
        if not organization_id or not branch_id or not device_uid:
            raise ValueError("Cloud sync organization, branch, and device UID are required for heartbeat telemetry")

        source_device_id = None
        device = db.query(Device).filter(Device.device_uid == device_uid).first()
        if device is not None:
            source_device_id = device.id

        payload = SystemHeartbeatService.build_payload(
            db,
            scheduler_running=scheduler_running,
            scheduler_job_count=scheduler_job_count,
        )
        payload.update({
            "organization_id": organization_id,
            "branch_id": branch_id,
            "device_uid": device_uid,
        })

        return SyncOutboxService.record_event(
            db,
            event_type=SyncEventType.SYSTEM_HEARTBEAT,
            aggregate_type="system",
            aggregate_id=None,
            organization_id=organization_id,
            branch_id=branch_id,
            source_device_id=source_device_id,
            payload=payload,
        )
