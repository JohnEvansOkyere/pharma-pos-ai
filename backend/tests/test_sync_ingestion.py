from __future__ import annotations

import hashlib
import json

import pytest
from fastapi import HTTPException

from app.api.endpoints.sync import ingest_sync_event
from app.core.config import settings
from app.models import Branch, Device, Organization
from app.models.sync_event import SyncEventType
from app.models.sync_ingestion import IngestedSyncEvent
from app.models.tenancy import DeviceStatus
from app.schemas.sync_ingestion import SyncIngestionRequest


def _payload_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@pytest.fixture()
def registered_device(db_session):
    organization = Organization(name="Sync Pharmacy")
    db_session.add(organization)
    db_session.flush()
    branch = Branch(
        organization_id=organization.id,
        name="Main Branch",
        code="MAIN",
    )
    db_session.add(branch)
    db_session.flush()
    device = Device(
        organization_id=organization.id,
        branch_id=branch.id,
        device_uid="sync-device-001",
        name="Main Branch Server",
        status=DeviceStatus.ACTIVE,
    )
    db_session.add(device)
    db_session.commit()
    return organization, branch, device


def _request(organization, branch, *, event_id: str = "11111111-1111-1111-1111-111111111111", sequence: int = 1):
    payload = {
        "sale_id": 10,
        "invoice_number": "INV-20260429-000010",
        "total_amount": "125.00",
    }
    return SyncIngestionRequest(
        event_id=event_id,
        organization_id=organization.id,
        branch_id=branch.id,
        device_uid="sync-device-001",
        local_sequence_number=sequence,
        event_type=SyncEventType.SALE_CREATED,
        aggregate_type="sale",
        aggregate_id=10,
        schema_version=1,
        payload=payload,
        payload_hash=_payload_hash(payload),
    )


@pytest.fixture(autouse=True)
def sync_token(monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_SYNC_REQUIRE_TOKEN", True)
    monkeypatch.setattr(settings, "CLOUD_SYNC_API_TOKEN", "test-sync-token")
    return "Bearer test-sync-token"


def _ingest(request: SyncIngestionRequest, *, db_session, authorization: str = "Bearer test-sync-token"):
    return ingest_sync_event(
        request,
        authorization=authorization,
        db=db_session,
    )


def test_ingest_sync_event_accepts_registered_device_event(db_session, registered_device):
    organization, branch, _device = registered_device

    response = _ingest(_request(organization, branch), db_session=db_session)

    ingested = db_session.query(IngestedSyncEvent).filter(
        IngestedSyncEvent.event_id == response.event_id
    ).one()

    assert response.accepted is True
    assert response.duplicate is False
    assert response.local_sequence_number == 1
    assert ingested.event_type == SyncEventType.SALE_CREATED
    assert ingested.payload["invoice_number"] == "INV-20260429-000010"
    assert ingested.duplicate_count == 0


def test_ingest_sync_event_is_idempotent_for_same_event_and_hash(db_session, registered_device):
    organization, branch, _device = registered_device
    request = _request(organization, branch)

    first_response = _ingest(request, db_session=db_session)
    duplicate_response = _ingest(request, db_session=db_session)

    ingested = db_session.query(IngestedSyncEvent).filter(
        IngestedSyncEvent.event_id == request.event_id
    ).one()

    assert first_response.duplicate is False
    assert duplicate_response.duplicate is True
    assert duplicate_response.ingested_event_id == first_response.ingested_event_id
    assert ingested.duplicate_count == 1
    assert ingested.last_duplicate_at is not None
    assert db_session.query(IngestedSyncEvent).count() == 1


def test_ingest_sync_event_rejects_same_event_id_with_different_hash(db_session, registered_device):
    organization, branch, _device = registered_device
    request = _request(organization, branch)
    _ingest(request, db_session=db_session)

    conflicting_request = _request(organization, branch)
    conflicting_request.payload = {"sale_id": 10, "invoice_number": "CHANGED"}
    conflicting_request.payload_hash = _payload_hash(conflicting_request.payload)

    with pytest.raises(HTTPException) as exc:
        _ingest(conflicting_request, db_session=db_session)

    assert exc.value.status_code == 409
    assert "different payload hash" in exc.value.detail


def test_ingest_sync_event_rejects_device_sequence_conflict(db_session, registered_device):
    organization, branch, _device = registered_device
    _ingest(_request(organization, branch), db_session=db_session)

    with pytest.raises(HTTPException) as exc:
        _ingest(
            _request(
                organization,
                branch,
                event_id="22222222-2222-2222-2222-222222222222",
                sequence=1,
            ),
            db_session=db_session,
        )

    assert exc.value.status_code == 409
    assert "sequence number" in exc.value.detail


def test_ingest_sync_event_rejects_inactive_device(db_session, registered_device):
    organization, branch, device = registered_device
    device.status = DeviceStatus.DISABLED
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        _ingest(_request(organization, branch), db_session=db_session)

    assert exc.value.status_code == 403
    assert "not active" in exc.value.detail


def test_ingest_sync_event_rejects_missing_sync_token(db_session, registered_device):
    organization, branch, _device = registered_device

    with pytest.raises(HTTPException) as exc:
        _ingest(_request(organization, branch), db_session=db_session, authorization=None)

    assert exc.value.status_code == 401
    assert "sync token" in exc.value.detail.lower()


def test_ingest_sync_event_rejects_invalid_sync_token(db_session, registered_device):
    organization, branch, _device = registered_device

    with pytest.raises(HTTPException) as exc:
        _ingest(_request(organization, branch), db_session=db_session, authorization="Bearer wrong-token")

    assert exc.value.status_code == 401
    assert "sync token" in exc.value.detail.lower()


def test_ingest_sync_event_fails_closed_when_sync_token_is_not_configured(
    db_session,
    registered_device,
    monkeypatch,
):
    organization, branch, _device = registered_device
    monkeypatch.setattr(settings, "CLOUD_SYNC_API_TOKEN", None)

    with pytest.raises(HTTPException) as exc:
        _ingest(_request(organization, branch), db_session=db_session)

    assert exc.value.status_code == 503
    assert "not configured" in exc.value.detail.lower()
