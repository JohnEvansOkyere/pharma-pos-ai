from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from app.api.endpoints.admin_tenancy import get_command_center
from app.models import Branch, Device, Organization
from app.models.sync_event import SyncEventType
from app.models.sync_ingestion import IngestedSyncEvent
from app.models.tenancy import DeviceStatus
from app.services.cloud_projection_service import CloudProjectionService
from app.services.sync_identity_service import build_aggregate_uid


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_command_center_surfaces_heartbeat_readiness(db_session, admin_user):
    organization = Organization(name="Command Center Pharmacy")
    db_session.add(organization)
    db_session.flush()
    branch = Branch(organization_id=organization.id, name="Main", code="MAIN")
    db_session.add(branch)
    db_session.flush()
    device = Device(
        organization_id=organization.id,
        branch_id=branch.id,
        device_uid="command-heartbeat-001",
        name="Main Server",
        status=DeviceStatus.ACTIVE,
    )
    db_session.add(device)
    db_session.commit()

    payload = {
        "device_uid": device.device_uid,
        "server_time": datetime.now(timezone.utc).isoformat(),
        "readiness_status": "critical",
        "app_version": "1.0.0",
        "environment": "production",
        "database_connected": False,
        "scheduler_enabled": True,
        "scheduler_running": False,
        "scheduler_job_count": 0,
        "cloud_sync_enabled": True,
        "cloud_sync_configured": True,
        "sync_pending_count": 12,
        "sync_failed_count": 2,
        "backup_is_recent": False,
        "restore_recovery_ready": False,
        "free_disk_bytes": 1_000_000_000,
        "total_disk_bytes": 20_000_000_000,
        "uptime_seconds": 3600,
    }
    event = IngestedSyncEvent(
        event_id="34343434-3434-3434-3434-343434343434",
        organization_id=organization.id,
        branch_id=branch.id,
        source_device_id=device.id,
        deployment_uid=device.deployment_uid,
        local_sequence_number=1,
        event_type=SyncEventType.SYSTEM_HEARTBEAT,
        aggregate_type="system",
        aggregate_id=None,
        aggregate_uid=build_aggregate_uid(device.deployment_uid, "system", None),
        schema_version=1,
        payload=payload,
        payload_hash=_hash(payload),
    )
    db_session.add(event)
    db_session.commit()
    CloudProjectionService.project_pending(db_session)

    command = get_command_center(expiry_warning_days=90, db=db_session, _=admin_user)

    assert command.totals.heartbeat_critical_devices == 1
    assert command.totals.heartbeat_ready_devices == 0
    assert command.last_heartbeat_at is not None
    assert command.organizations[0].readiness_status == "critical"
    assert command.organizations[0].heartbeat_critical_count == 1
    assert any(item.kind == "heartbeat_critical" for item in command.attention)
