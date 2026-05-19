from __future__ import annotations

from app.core.config import settings
from app.models import Branch, Device, Organization
from app.models.sync_event import SyncEvent, SyncEventType
from app.models.tenancy import DeviceStatus
from app.services.system_heartbeat_service import SystemHeartbeatService


def test_system_heartbeat_enqueue_records_local_health_event(db_session, monkeypatch):
    organization = Organization(name="Heartbeat Pharmacy")
    db_session.add(organization)
    db_session.flush()
    branch = Branch(organization_id=organization.id, name="Main", code="MAIN")
    db_session.add(branch)
    db_session.flush()
    device = Device(
        organization_id=organization.id,
        branch_id=branch.id,
        device_uid="heartbeat-device-001",
        name="Main Server",
        status=DeviceStatus.ACTIVE,
    )
    db_session.add(device)
    db_session.commit()

    monkeypatch.setattr(settings, "CLOUD_SYNC_ENABLED", True)
    monkeypatch.setattr(settings, "CLOUD_SYNC_INGEST_URL", "https://cloud.example/api/sync/ingest")
    monkeypatch.setattr(settings, "CLOUD_SYNC_ORGANIZATION_ID", organization.id)
    monkeypatch.setattr(settings, "CLOUD_SYNC_BRANCH_ID", branch.id)
    monkeypatch.setattr(settings, "CLOUD_SYNC_DEVICE_UID", device.device_uid)

    event = SystemHeartbeatService.enqueue_heartbeat(
        db_session,
        scheduler_running=True,
        scheduler_job_count=9,
    )
    db_session.commit()
    saved = db_session.query(SyncEvent).filter(SyncEvent.id == event.id).one()

    assert saved.event_type == SyncEventType.SYSTEM_HEARTBEAT
    assert saved.organization_id == organization.id
    assert saved.branch_id == branch.id
    assert saved.source_device_id == device.id
    assert saved.payload["device_uid"] == device.device_uid
    assert saved.payload["database_connected"] is True
    assert saved.payload["scheduler_running"] is True
    assert saved.payload["scheduler_job_count"] == 9
    assert saved.payload["cloud_sync_enabled"] is True
    assert saved.payload["cloud_sync_configured"] is True
    assert saved.payload["readiness_status"] in {"ready", "warning"}
    assert "free_disk_bytes" in saved.payload
