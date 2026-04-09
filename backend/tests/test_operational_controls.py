from __future__ import annotations

from decimal import Decimal

from app.api.endpoints.sales import create_sale, get_end_of_day_closeout, refund_sale, void_sale
from app.models.activity_log import ActivityLog
from app.models.sale import SaleStatus
from app.models.stock_adjustment import StockAdjustment, AdjustmentType
from app.schemas.sale import SaleActionRequest, SaleCreate, SaleItemCreate


def test_void_sale_restores_stock_and_marks_sale_cancelled(
    db_session,
    admin_user,
    category,
    product_factory,
    batch_factory,
):
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

    assert voided_sale.status == SaleStatus.CANCELLED
    assert batch.quantity == 5
    assert product.total_stock == 5
    assert return_adjustment is not None
    assert return_adjustment.quantity == 2
    assert audit_entry is not None


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
