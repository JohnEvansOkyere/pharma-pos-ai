"""
Schemas for local system operations such as backup status and diagnostics.
"""
from typing import Optional
from pydantic import BaseModel


class BackupStatus(BaseModel):
    platform: str
    backup_dir: str
    latest_backup_path: Optional[str] = None
    latest_backup_exists: bool
    latest_backup_time: Optional[str] = None
    latest_backup_size_bytes: Optional[int] = None
    latest_backup_age_hours: Optional[float] = None
    backup_is_recent: bool
    retention_days: int
    trigger_available: bool
    schedule_helper_available: bool


class BackupTriggerResult(BaseModel):
    success: bool
    message: str
    backup: BackupStatus


class SystemDiagnostics(BaseModel):
    platform: str
    app_version: str
    environment: str
    database_backend: str
    database_connected: bool
    scheduler_enabled: bool
    scheduler_running: bool
    scheduler_job_count: int
    backup_dir: str
    latest_backup_exists: bool
    latest_backup_time: Optional[str] = None
    backup_is_recent: bool
    frontend_dist_available: bool
    windows_backup_task_helper_available: bool
    linux_backup_cron_helper_available: bool
