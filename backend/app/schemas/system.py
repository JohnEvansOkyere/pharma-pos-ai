"""
Schemas for local system operations such as backup status and diagnostics.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
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
    cloud_sync_enabled: bool
    cloud_sync_configured: bool
    sync_pending_count: int
    sync_failed_count: int
    sync_sent_count: int
    sync_last_sent_at: Optional[str] = None


class SyncStatus(BaseModel):
    enabled: bool
    configured: bool
    pending_count: int
    failed_count: int
    sent_count: int
    last_sent_at: Optional[str] = None


class SyncRunResult(BaseModel):
    attempted: int
    sent: int
    failed: int
    skipped: int
    message: str


class AuditLogEntry(BaseModel):
    id: int
    organization_id: Optional[int] = None
    branch_id: Optional[int] = None
    source_device_id: Optional[int] = None
    user_id: Optional[int] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    description: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    hash_version: Optional[int] = None
    previous_hash: Optional[str] = None
    current_hash: Optional[str] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[AuditLogEntry]


class AuditIntegrityIssue(BaseModel):
    log_id: Optional[int] = None
    organization_id: Optional[int] = None
    issue_type: str
    message: str


class AuditIntegrityStatus(BaseModel):
    scope: str
    organization_id: Optional[int] = None
    checked_at: datetime
    valid: bool
    total_count: int
    sealed_count: int
    unsealed_count: int
    unsealed_after_chain_count: int
    invalid_count: int
    first_invalid_log_id: Optional[int] = None
    latest_log_id: Optional[int] = None
    latest_hash: Optional[str] = None
    issues: List[AuditIntegrityIssue]
