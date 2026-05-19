from __future__ import annotations

from decimal import Decimal

from app.api.endpoints.system_ops import enqueue_cloud_snapshot
from app.models.activity_log import ActivityLog
from app.models.sync_event import SyncEvent, SyncEventType


def test_full_snapshot_enqueue_records_products_and_batches(
    db_session,
    manager_user,
    category,
    product_factory,
    batch_factory,
):
    product = product_factory(category.id, name="Snapshot Product", sku="SNAP-001")
    product.cost_price = Decimal("1.25")
    product.selling_price = Decimal("2.50")
    product.low_stock_threshold = 4
    product.reorder_level = 12
    sellable_batch = batch_factory(
        product.id,
        batch_number="SNAP-B1",
        quantity=8,
        expiry_offset_days=180,
    )
    quarantined_batch = batch_factory(
        product.id,
        batch_number="SNAP-Q1",
        quantity=5,
        expiry_offset_days=180,
    )
    quarantined_batch.is_quarantined = True
    inactive_product = product_factory(category.id, name="Inactive Snapshot", sku="SNAP-INACTIVE")
    inactive_product.is_active = False
    db_session.commit()

    result = enqueue_cloud_snapshot(db=db_session, current_user=manager_user)
    events = db_session.query(SyncEvent).order_by(SyncEvent.local_sequence_number.asc()).all()
    audit_entry = db_session.query(ActivityLog).filter(
        ActivityLog.action == "enqueue_cloud_snapshot"
    ).one()

    assert result.success is True
    assert result.product_event_count == 1
    assert result.batch_event_count == 2
    assert result.total_event_count == 3
    assert [event.event_type for event in events] == [
        SyncEventType.PRODUCT_CREATED,
        SyncEventType.PRODUCT_BATCH_CREATED,
        SyncEventType.PRODUCT_BATCH_CREATED,
    ]
    product_event = events[0]
    assert product_event.aggregate_id == product.id
    assert product_event.payload["total_stock"] == 8
    assert product_event.payload["snapshot_reason"] == "full_catalog_snapshot"
    assert events[1].payload["batch_id"] == sellable_batch.id
    assert events[1].payload["stock_after"] == 8
    assert events[2].payload["batch_id"] == quarantined_batch.id
    assert events[2].payload["is_quarantined"] is True
    product_event_ids = [
        event.aggregate_id for event in events if event.event_type == SyncEventType.PRODUCT_CREATED
    ]
    assert inactive_product.id not in product_event_ids
    assert audit_entry.current_hash is not None


def test_full_snapshot_enqueue_can_include_inactive_products(
    db_session,
    manager_user,
    category,
    product_factory,
):
    product = product_factory(category.id, name="Inactive Included", sku="SNAP-INCL")
    product.is_active = False
    db_session.commit()

    result = enqueue_cloud_snapshot(
        include_inactive=True,
        db=db_session,
        current_user=manager_user,
    )
    event = db_session.query(SyncEvent).filter(
        SyncEvent.event_type == SyncEventType.PRODUCT_CREATED,
        SyncEvent.aggregate_id == product.id,
    ).one()

    assert result.product_event_count == 1
    assert result.batch_event_count == 0
    assert event.payload["is_active"] is False
