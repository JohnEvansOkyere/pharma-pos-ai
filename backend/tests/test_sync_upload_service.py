from __future__ import annotations

from app.core.config import settings
from app.models import Branch, Device, Organization, SyncEvent
from app.models.sync_event import SyncEventStatus, SyncEventType
from app.models.tenancy import DeviceStatus
from app.services.sync_outbox_service import SyncOutboxService
from app.services.sync_upload_service import SyncUploadService


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "ok"):
        self.status_code = status_code
        self.text = text


class _FakeClient:
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, *, json, headers):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return _FakeResponse(202)


def _tenant_device(db_session):
    organization = Organization(name="Upload Pharmacy")
    db_session.add(organization)
    db_session.flush()
    branch = Branch(organization_id=organization.id, name="Main", code="MAIN")
    db_session.add(branch)
    db_session.flush()
    device = Device(
        organization_id=organization.id,
        branch_id=branch.id,
        device_uid="upload-device-001",
        name="Main Server",
        status=DeviceStatus.ACTIVE,
    )
    db_session.add(device)
    db_session.commit()
    return organization, branch, device


def test_upload_pending_marks_event_sent(monkeypatch, db_session):
    organization, branch, device = _tenant_device(db_session)
    _FakeClient.calls = []
    monkeypatch.setattr("app.services.sync_upload_service.httpx.Client", _FakeClient)
    monkeypatch.setattr(settings, "CLOUD_SYNC_ENABLED", True)
    monkeypatch.setattr(settings, "CLOUD_SYNC_INGEST_URL", "https://example.supabase.co/functions/v1/sync-ingest")
    monkeypatch.setattr(settings, "CLOUD_SYNC_API_TOKEN", "secret-token")

    event = SyncOutboxService.record_event(
        db_session,
        event_type=SyncEventType.SALE_CREATED,
        aggregate_type="sale",
        aggregate_id=1,
        organization_id=organization.id,
        branch_id=branch.id,
        source_device_id=device.id,
        payload={"sale_id": 1, "total_amount": "10.00"},
    )
    db_session.commit()

    result = SyncUploadService.upload_pending(db_session)
    db_session.refresh(event)

    assert result["attempted"] == 1
    assert result["sent"] == 1
    assert event.status == SyncEventStatus.SENT
    assert event.sent_at is not None
    assert event.acknowledged_at is not None
    assert _FakeClient.calls[0]["json"]["device_uid"] == "upload-device-001"
    assert _FakeClient.calls[0]["headers"]["Authorization"] == "Bearer secret-token"


def test_upload_pending_marks_missing_identity_failed(monkeypatch, db_session):
    monkeypatch.setattr(settings, "CLOUD_SYNC_ENABLED", True)
    monkeypatch.setattr(settings, "CLOUD_SYNC_INGEST_URL", "https://example.supabase.co/functions/v1/sync-ingest")
    monkeypatch.setattr(settings, "CLOUD_SYNC_ORGANIZATION_ID", None)
    monkeypatch.setattr(settings, "CLOUD_SYNC_BRANCH_ID", None)
    monkeypatch.setattr(settings, "CLOUD_SYNC_DEVICE_UID", None)

    event = SyncOutboxService.record_event(
        db_session,
        event_type=SyncEventType.PRODUCT_CREATED,
        aggregate_type="product",
        aggregate_id=1,
        payload={"product_id": 1, "sku": "NOIDENT-001"},
    )
    db_session.commit()

    result = SyncUploadService.upload_pending(db_session)
    saved_event = db_session.query(SyncEvent).filter(SyncEvent.id == event.id).one()

    assert result["failed"] == 1
    assert saved_event.status == SyncEventStatus.FAILED
    assert saved_event.retry_count == 1
    assert "missing organization" in saved_event.last_error
