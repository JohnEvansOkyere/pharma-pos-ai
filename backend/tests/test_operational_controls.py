from __future__ import annotations

from decimal import Decimal

from app.api.endpoints.sales import create_sale, get_end_of_day_closeout, refund_sale, void_sale
from app.core.config import settings
from app.models.activity_log import ActivityLog
from app.models.inventory_movement import InventoryMovement, InventoryMovementType
from app.models.sale import SaleReversal, SaleReversalType, SaleStatus
from app.models.stock_adjustment import StockAdjustment, AdjustmentType
from app.schemas.sale import SaleActionRequest, SaleCreate, SaleItemCreate


def test_void_sale_restores_stock_and_marks_sale_cancelled(
    db_session,
    admin_user,
    category,
    product_factory,
    batch_factory,
    assign_tenant_scope,
    monkeypatch,
):
    organization, branch, _other_branch = assign_tenant_scope(admin_user)
    product = product_factory(category.id, name="Voidable Product", sku="VOID-001")
    product.cost_price = Decimal("2.50")
    product.selling_price = Decimal("4.00")
    db_session.commit()
    db_session.refresh(product)

    batch = batch_factory(
        product.id,
        batch_number="VOID-B1",
        quantity=5,
        expiry_offset_days=120,
    )
    product.organization_id = organization.id
    product.branch_id = branch.id
    batch.organization_id = organization.id
    batch.branch_id = branch.id
    db_session.commit()
    monkeypatch.setattr(settings, "APP_MODE", "online_pos")

    sale = create_sale(
        SaleCreate(
            items=[SaleItemCreate(product_id=product.id, quantity=2, unit_price=4.0, discount_amount=0.0)],
            discount_amount=0.0,
            tax_amount=0.0,
            amount_paid=8.0,
        ),
        db=db_session,
        current_user=admin_user,
    )

    voided_sale = void_sale(
        sale.id,
        SaleActionRequest(reason="Operator entered wrong quantity"),
        db=db_session,
        current_user=admin_user,
    )

    db_session.refresh(batch)
    db_session.refresh(product)
    audit_entry = (
        db_session.query(ActivityLog)
        .filter(ActivityLog.action == "cancelled_sale", ActivityLog.entity_id == sale.id)
        .order_by(ActivityLog.id.desc())
        .first()
    )
    return_adjustment = (
        db_session.query(StockAdjustment)
        .filter(
            StockAdjustment.product_id == product.id,
            StockAdjustment.adjustment_type == AdjustmentType.RETURN,
        )
        .order_by(StockAdjustment.id.desc())
        .first()
    )
    reversal_movement = (
        db_session.query(InventoryMovement)
        .filter(
            InventoryMovement.movement_type == InventoryMovementType.SALE_REVERSED,
            InventoryMovement.source_document_type == "stock_adjustment",
        )
        .order_by(InventoryMovement.id.desc())
        .first()
    )
    reversal_record = db_session.query(SaleReversal).filter(SaleReversal.sale_id == sale.id).one()

    assert voided_sale.status == SaleStatus.CANCELLED
    assert batch.quantity == 5
    assert product.total_stock == 5
    assert return_adjustment is not None
    assert return_adjustment.quantity == 2
    assert return_adjustment.organization_id == organization.id
    assert return_adjustment.branch_id == branch.id
    assert reversal_movement is not None
    assert reversal_movement.organization_id == organization.id
    assert reversal_movement.branch_id == branch.id
    assert reversal_movement.batch_id == batch.id
    assert reversal_movement.quantity_delta == 2
    assert reversal_movement.stock_after == 5
    assert reversal_movement.source_document_id == return_adjustment.id
    assert reversal_record.reversal_type == SaleReversalType.VOID
    assert reversal_record.organization_id == organization.id
    assert reversal_record.branch_id == branch.id
    assert reversal_record.reason == "Operator entered wrong quantity"
    assert reversal_record.restored_quantity == 2
    assert reversal_record.total_amount == Decimal("8.00")
    assert reversal_record.performed_by == admin_user.id
    assert audit_entry is not None
    assert audit_entry.organization_id == organization.id
    assert audit_entry.branch_id == branch.id


def test_sale_reversal_scopes_reconstructed_batch(
    db_session,
    admin_user,
    category,
    product_factory,
    batch_factory,
    assign_tenant_scope,
    monkeypatch,
):
    organization, branch, _other_branch = assign_tenant_scope(admin_user)
    product = product_factory(category.id, name="Reconstructed Batch Product", sku="RESTORE-BATCH")
    product.cost_price = Decimal("2.50")
    product.selling_price = Decimal("4.00")
    batch = batch_factory(
        product.id,
        batch_number="RESTORE-ORIGINAL",
        quantity=5,
        expiry_offset_days=120,
    )
    product.organization_id = organization.id
    product.branch_id = branch.id
    batch.organization_id = organization.id
    batch.branch_id = branch.id
    db_session.commit()
    monkeypatch.setattr(settings, "APP_MODE", "online_pos")

    sale = create_sale(
        SaleCreate(
            items=[SaleItemCreate(product_id=product.id, quantity=2, unit_price=4.0, discount_amount=0.0)],
            discount_amount=0.0,
            tax_amount=0.0,
            amount_paid=8.0,
        ),
        db=db_session,
        current_user=admin_user,
    )
    batch.batch_number = "RESTORE-RENAMED"
    db_session.commit()

    void_sale(
        sale.id,
        SaleActionRequest(reason="Rebuild missing original batch"),
        db=db_session,
        current_user=admin_user,
    )

    restored_batch = db_session.query(type(batch)).filter(
        type(batch).product_id == product.id,
        type(batch).batch_number == "RESTORE-ORIGINAL",
    ).one()

    assert restored_batch.organization_id == organization.id
    assert restored_batch.branch_id == branch.id
    assert restored_batch.quantity == 2


def test_end_of_day_closeout_includes_completed_and_refunded_sales(
    db_session,
    admin_user,
    category,
    product_factory,
    batch_factory,
):
    product = product_factory(category.id, name="Closeout Product", sku="CLOSE-001")
    product.cost_price = Decimal("1.50")
    product.selling_price = Decimal("3.00")
    db_session.commit()
    db_session.refresh(product)

    batch_factory(
        product.id,
        batch_number="CLOSE-B1",
        quantity=10,
        expiry_offset_days=90,
    )

    sale = create_sale(
        SaleCreate(
            items=[SaleItemCreate(product_id=product.id, quantity=2, unit_price=3.0, discount_amount=0.0)],
            discount_amount=0.0,
            tax_amount=0.0,
            amount_paid=6.0,
        ),
        db=db_session,
        current_user=admin_user,
    )

    refund_sale(
        sale.id,
        SaleActionRequest(reason="Customer returned sealed pack"),
        db=db_session,
        current_user=admin_user,
    )
    reversal_record = db_session.query(SaleReversal).filter(SaleReversal.sale_id == sale.id).one()

    second_sale = create_sale(
        SaleCreate(
            items=[SaleItemCreate(product_id=product.id, quantity=1, unit_price=3.0, discount_amount=0.0)],
            discount_amount=0.0,
            tax_amount=0.0,
            amount_paid=3.0,
        ),
        db=db_session,
        current_user=admin_user,
    )

    closeout = get_end_of_day_closeout(db=db_session, current_user=admin_user)

    assert second_sale.status == SaleStatus.COMPLETED
    assert closeout["completed_sales_count"] == 1
    assert closeout["refunded_sales_count"] == 1
    assert closeout["completed_revenue"] == 3.0
    assert closeout["refunded_revenue"] == 6.0
    assert closeout["cash_revenue"] == 3.0
    assert reversal_record.reversal_type == SaleReversalType.REFUND
    assert reversal_record.reason == "Customer returned sealed pack"
    assert reversal_record.restored_quantity == 2
    assert reversal_record.total_amount == Decimal("6.00")
