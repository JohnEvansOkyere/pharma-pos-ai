from __future__ import annotations

from decimal import Decimal

from app.api.endpoints.sales import create_sale, get_today_sales_summary
from app.models.activity_log import ActivityLog
from app.schemas.sale import SaleCreate, SaleItemCreate


def test_create_sale_rounds_and_stores_decimal_money(
    db_session,
    cashier_user,
    category,
    product_factory,
    batch_factory,
):
    product = product_factory(category.id, name="Amoxicillin", sku="AMOX-250")
    product.cost_price = Decimal("1.01")
    product.selling_price = Decimal("1.23")
    db_session.commit()
    db_session.refresh(product)

    batch_factory(
        product.id,
        batch_number="AMOX-B1",
        quantity=5,
        expiry_offset_days=365,
    )

    sale = create_sale(
        SaleCreate(
            items=[
                SaleItemCreate(
                    product_id=product.id,
                    quantity=2,
                    unit_price=1.23,
                    discount_amount=0.01,
                )
            ],
            discount_amount=0.01,
            tax_amount=0.05,
            amount_paid=3.00,
        ),
        db=db_session,
        current_user=cashier_user,
    )

    db_session.refresh(sale)
    audit_entry = (
        db_session.query(ActivityLog)
        .filter(ActivityLog.action == "create_sale", ActivityLog.entity_id == sale.id)
        .order_by(ActivityLog.id.desc())
        .first()
    )

    assert sale.subtotal == Decimal("2.45")
    assert sale.discount_amount == Decimal("0.01")
    assert sale.tax_amount == Decimal("0.05")
    assert sale.total_amount == Decimal("2.49")
    assert sale.amount_paid == Decimal("3.00")
    assert sale.change_amount == Decimal("0.51")
    assert sale.items[0].unit_price == Decimal("1.23")
    assert sale.items[0].total_price == Decimal("2.45")
    assert audit_entry is not None


def test_today_sales_summary_uses_aggregate_money_totals(
    db_session,
    cashier_user,
    category,
    product_factory,
    batch_factory,
):
    product = product_factory(category.id, name="Cetrizine", sku="CET-010")
    product.cost_price = Decimal("2.00")
    product.selling_price = Decimal("3.50")
    db_session.commit()
    db_session.refresh(product)

    batch_factory(
        product.id,
        batch_number="CET-B1",
        quantity=10,
        expiry_offset_days=180,
    )

    create_sale(
        SaleCreate(
            items=[SaleItemCreate(product_id=product.id, quantity=2, unit_price=3.50, discount_amount=0.00)],
            discount_amount=0.00,
            tax_amount=0.00,
            amount_paid=7.00,
        ),
        db=db_session,
        current_user=cashier_user,
    )

    summary = get_today_sales_summary(db=db_session, current_user=cashier_user)

    assert summary["total_sales"] == 1
    assert summary["total_revenue"] == 7.0
    assert summary["total_profit"] == 3.0
    assert summary["total_items_sold"] == 2
