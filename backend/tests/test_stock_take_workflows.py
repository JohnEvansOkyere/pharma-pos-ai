from __future__ import annotations

from app.api.endpoints.stock_takes import complete_stock_take, create_stock_take
from app.core.config import settings
from app.models.activity_log import ActivityLog
from app.models.inventory_movement import InventoryMovement, InventoryMovementType
from app.models.product import Product, ProductBatch
from app.models.stock_adjustment import AdjustmentType, StockAdjustment
from app.models.stock_take import StockTakeStatus
from app.schemas.stock_take import StockTakeComplete, StockTakeCreate, StockTakeItemCreate

import pytest
from fastapi import HTTPException


def test_complete_stock_take_applies_batch_correction_with_audit_and_movement(
    db_session,
    manager_user,
    category,
    product_factory,
    batch_factory,
    assign_tenant_scope,
    monkeypatch,
):
    organization, branch, _other_branch = assign_tenant_scope(manager_user)
    product = product_factory(category.id, name="Counted Product", sku="COUNT-001")
    batch = batch_factory(
        product.id,
        batch_number="COUNT-B1",
        quantity=10,
        expiry_offset_days=180,
    )
    product.organization_id = organization.id
    product.branch_id = branch.id
    batch.organization_id = organization.id
    batch.branch_id = branch.id
    db_session.commit()
    monkeypatch.setattr(settings, "APP_MODE", "online_pos")

    stock_take = create_stock_take(
        StockTakeCreate(
            reason="Monthly physical count",
            items=[
                StockTakeItemCreate(
                    product_id=product.id,
                    batch_id=batch.id,
                    counted_quantity=7,
                    reason="Shelf count variance",
                )
            ],
        ),
        db=db_session,
        current_user=manager_user,
    )

    completed = complete_stock_take(
        stock_take.id,
        StockTakeComplete(notes="Approved by manager"),
        db=db_session,
        current_user=manager_user,
    )

    refreshed_batch = db_session.query(ProductBatch).filter(ProductBatch.id == batch.id).one()
    refreshed_product = db_session.query(Product).filter(Product.id == product.id).one()
    adjustment = db_session.query(StockAdjustment).filter(
        StockAdjustment.adjustment_type == AdjustmentType.CORRECTION,
        StockAdjustment.batch_id == batch.id,
    ).one()
    movement = db_session.query(InventoryMovement).filter(
        InventoryMovement.source_document_type == "stock_take",
        InventoryMovement.source_document_id == stock_take.id,
    ).one()
    audit_entry = db_session.query(ActivityLog).filter(
        ActivityLog.action == "complete_stock_take",
        ActivityLog.entity_id == stock_take.id,
    ).one()
    assert completed.status == StockTakeStatus.COMPLETED
    assert completed.organization_id == organization.id
    assert completed.branch_id == branch.id
    assert completed.items[0].organization_id == organization.id
    assert completed.items[0].branch_id == branch.id
    assert completed.completed_by == manager_user.id
    assert refreshed_batch.quantity == 7
    assert refreshed_product.total_stock == 7
    assert adjustment.quantity == 3
    assert adjustment.reason == "Shelf count variance"
    assert adjustment.organization_id == organization.id
    assert adjustment.branch_id == branch.id
    assert movement.movement_type == InventoryMovementType.STOCK_CORRECTION
    assert movement.organization_id == organization.id
    assert movement.branch_id == branch.id
    assert movement.quantity_delta == -3
    assert movement.stock_after == 7
    assert audit_entry.extra_data["movement_count"] == 1
    assert audit_entry.extra_data["total_variance"] == -3
    assert audit_entry.organization_id == organization.id
    assert audit_entry.branch_id == branch.id


def test_complete_stock_take_rejects_stale_count_when_batch_changed(
    db_session,
    manager_user,
    category,
    product_factory,
    batch_factory,
):
    product = product_factory(category.id, name="Stale Count Product", sku="STALE-001")
    batch = batch_factory(
        product.id,
        batch_number="STALE-B1",
        quantity=10,
        expiry_offset_days=180,
    )

    stock_take = create_stock_take(
        StockTakeCreate(
            reason="Cycle count",
            items=[
                StockTakeItemCreate(
                    product_id=product.id,
                    batch_id=batch.id,
                    counted_quantity=8,
                    reason="Physical count",
                )
            ],
        ),
        db=db_session,
        current_user=manager_user,
    )

    batch.quantity = 9
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        complete_stock_take(
            stock_take.id,
            StockTakeComplete(),
            db=db_session,
            current_user=manager_user,
        )

    refreshed_batch = db_session.query(ProductBatch).filter(ProductBatch.id == batch.id).one()

    assert exc.value.status_code == 409
    assert "changed after the count" in exc.value.detail
    assert refreshed_batch.quantity == 9
    assert db_session.query(InventoryMovement).filter(
        InventoryMovement.source_document_type == "stock_take",
        InventoryMovement.source_document_id == stock_take.id,
    ).count() == 0
