from __future__ import annotations

from decimal import Decimal

from app.api.endpoints.dashboard import get_expiring_products, get_financial_kpis, get_low_stock_items
from app.api.endpoints.sales import create_sale
from app.schemas.sale import SaleCreate, SaleItemCreate


def test_financial_kpis_returns_values_after_sales(
    db_session,
    admin_user,
    category,
    product_factory,
    batch_factory,
):
    product = product_factory(category.id, name="Dashboard Product", sku="DASH-001")
    product.cost_price = Decimal("2.00")
    product.selling_price = Decimal("3.50")
    db_session.commit()
    db_session.refresh(product)

    batch_factory(
        product.id,
        batch_number="DASH-B1",
        quantity=4,
        expiry_offset_days=15,
    )

    create_sale(
        SaleCreate(
            items=[SaleItemCreate(product_id=product.id, quantity=1, unit_price=3.50, discount_amount=0.00)],
            discount_amount=0.00,
            tax_amount=0.00,
            amount_paid=3.50,
        ),
        db=db_session,
        current_user=admin_user,
    )

    financial = get_financial_kpis(days=30, db=db_session, current_user=admin_user)
    expiring = get_expiring_products(days=30, limit=10, db=db_session, current_user=admin_user)
    low_stock = get_low_stock_items(limit=10, db=db_session, current_user=admin_user)

    assert financial["total_revenue"] == 3.5
    assert financial["gross_profit"] == 1.5
    assert financial["profit_margin"] > 0
    assert len(expiring) == 1
    assert expiring[0]["product_id"] == product.id
    assert len(low_stock) == 1
    assert low_stock[0]["product_id"] == product.id
