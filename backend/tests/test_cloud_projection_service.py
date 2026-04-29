from __future__ import annotations

import hashlib
import json

from app.models import Branch, Device, Organization
from app.models.cloud_projection import CloudInventoryMovementFact, CloudSaleFact
from app.models.sync_event import SyncEventType
from app.models.sync_ingestion import IngestedSyncEvent
from app.models.tenancy import DeviceStatus
from app.services.cloud_projection_service import CloudProjectionService


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _tenant_device(db_session):
    organization = Organization(name="Projection Pharmacy")
    db_session.add(organization)
    db_session.flush()
    branch = Branch(organization_id=organization.id, name="Main", code="MAIN")
    db_session.add(branch)
    db_session.flush()
    device = Device(
        organization_id=organization.id,
        branch_id=branch.id,
        device_uid="projection-device-001",
        name="Main Server",
        status=DeviceStatus.ACTIVE,
    )
    db_session.add(device)
    db_session.commit()
    return organization, branch, device


def _ingested_event(
    db_session,
    organization,
    branch,
    device,
    *,
    event_id: str,
    sequence: int,
    event_type: SyncEventType,
    aggregate_type: str,
    aggregate_id: int,
    payload: dict,
) -> IngestedSyncEvent:
    event = IngestedSyncEvent(
        event_id=event_id,
        organization_id=organization.id,
        branch_id=branch.id,
        source_device_id=device.id,
        local_sequence_number=sequence,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        schema_version=1,
        payload=payload,
        payload_hash=_hash(payload),
        duplicate_count=0,
    )
    db_session.add(event)
    db_session.commit()
    return event


def test_project_sale_created_builds_cloud_sale_fact_idempotently(db_session):
    organization, branch, device = _tenant_device(db_session)
    payload = {
        "sale_id": 25,
        "invoice_number": "INV-20260429-000025",
        "payment_method": "cash",
        "total_amount": "80.50",
        "items": [
            {"product_id": 1, "quantity": 2},
            {"product_id": 2, "quantity": 1},
        ],
    }
    event = _ingested_event(
        db_session,
        organization,
        branch,
        device,
        event_id="33333333-3333-3333-3333-333333333333",
        sequence=1,
        event_type=SyncEventType.SALE_CREATED,
        aggregate_type="sale",
        aggregate_id=25,
        payload=payload,
    )

    result = CloudProjectionService.project_pending(db_session)
    second_result = CloudProjectionService.project_pending(db_session)
    fact = db_session.query(CloudSaleFact).filter(CloudSaleFact.source_event_id == event.id).one()

    assert result["attempted"] == 1
    assert result["projected"] == 1
    assert second_result["attempted"] == 0
    assert fact.organization_id == organization.id
    assert fact.branch_id == branch.id
    assert fact.local_sale_id == 25
    assert fact.invoice_number == "INV-20260429-000025"
    assert fact.payment_method == "cash"
    assert fact.item_count == 2
    assert str(fact.total_amount) == "80.50"
    assert event.projected_at is not None
    assert db_session.query(CloudSaleFact).count() == 1


def test_project_stock_received_builds_inventory_movement_fact(db_session):
    organization, branch, device = _tenant_device(db_session)
    payload = {
        "product_id": 15,
        "batch_id": 4,
        "stock_adjustment_id": 8,
        "batch_number": "BATCH-001",
        "quantity": 30,
        "previous_stock": 10,
        "new_stock": 40,
    }
    event = _ingested_event(
        db_session,
        organization,
        branch,
        device,
        event_id="44444444-4444-4444-4444-444444444444",
        sequence=1,
        event_type=SyncEventType.STOCK_RECEIVED,
        aggregate_type="stock_adjustment",
        aggregate_id=8,
        payload=payload,
    )

    result = CloudProjectionService.project_pending(db_session)
    fact = db_session.query(CloudInventoryMovementFact).filter(
        CloudInventoryMovementFact.source_event_id == event.id
    ).one()

    assert result["projected"] == 1
    assert fact.event_type == SyncEventType.STOCK_RECEIVED.value
    assert fact.local_product_id == 15
    assert fact.local_batch_id == 4
    assert fact.quantity_delta == 30
    assert fact.stock_after == 40
    assert event.projected_at is not None


def test_projection_status_counts_pending_projected_and_failed(db_session):
    organization, branch, device = _tenant_device(db_session)
    _ingested_event(
        db_session,
        organization,
        branch,
        device,
        event_id="55555555-5555-5555-5555-555555555555",
        sequence=1,
        event_type=SyncEventType.SUPPLIER_CREATED,
        aggregate_type="supplier",
        aggregate_id=2,
        payload={"supplier_id": 2, "name": "Supplier"},
    )

    before = CloudProjectionService.status(db_session)
    CloudProjectionService.project_pending(db_session)
    after = CloudProjectionService.status(db_session)

    assert before["unprojected_count"] == 1
    assert after["unprojected_count"] == 0
    assert after["projected_count"] == 1
