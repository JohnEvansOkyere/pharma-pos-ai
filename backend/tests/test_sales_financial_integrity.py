from __future__ import annotations

from decimal import Decimal

import pytest

from app.api.endpoints.sales import create_sale, get_today_sales_summary
from app.models.activity_log import ActivityLog
from app.models.inventory_movement import InventoryMovement
from app.models.product import ProductBatch
from app.models.sale import Sale
from app.models.sale import SalePricingMode
from app.models.sync_event import SyncEvent, SyncEventType
from app.services.audit_service import AuditService
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


def test_create_sale_uses_wholesale_prices_when_sale_mode_is_wholesale(
    db_session,
    cashier_user,
    category,
    product_factory,
    batch_factory,
):
    product = product_factory(category.id, name="Wholesale Amox", sku="WH-AMOX-250")
    product.cost_price = Decimal("70.00")
    product.selling_price = Decimal("80.00")
    product.wholesale_price = Decimal("75.00")
    db_session.commit()
    db_session.refresh(product)

    batch_factory(
        product.id,
        batch_number="WH-AMOX-B1",
        quantity=10,
        expiry_offset_days=365,
    )

    sale = create_sale(
        SaleCreate(
            pricing_mode=SalePricingMode.WHOLESALE,
            items=[
                SaleItemCreate(
                    product_id=product.id,
                    quantity=2,
                    unit_price=999.99,
                    discount_amount=0.00,
                )
            ],
            discount_amount=0.00,
            tax_amount=0.00,
            amount_paid=150.00,
        ),
        db=db_session,
        current_user=cashier_user,
    )

    db_session.refresh(sale)

    assert sale.pricing_mode == SalePricingMode.WHOLESALE
    assert sale.items[0].unit_price == Decimal("75.00")
    assert sale.total_amount == Decimal("150.00")


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


def test_create_sale_records_pending_sync_event(
    db_session,
    cashier_user,
    category,
    product_factory,
    batch_factory,
):
    product = product_factory(category.id, name="Sync Sale Product", sku="SYNC-SALE-001")
    batch_factory(
        product.id,
        batch_number="SYNC-SALE-B1",
        quantity=5,
        expiry_offset_days=180,
    )

    sale = create_sale(
        SaleCreate(
            items=[SaleItemCreate(product_id=product.id, quantity=2, unit_price=3.50, discount_amount=0.00)],
            discount_amount=0.00,
            tax_amount=0.00,
            amount_paid=7.00,
        ),
        db=db_session,
        current_user=cashier_user,
    )

    sync_event = db_session.query(SyncEvent).filter(
        SyncEvent.event_type == SyncEventType.SALE_CREATED,
        SyncEvent.aggregate_type == "sale",
        SyncEvent.aggregate_id == sale.id,
    ).one()

    assert sync_event.local_sequence_number == 1
    assert sync_event.payload["sale_id"] == sale.id
    assert sync_event.payload["invoice_number"] == sale.invoice_number
    assert sync_event.payload["items"][0]["quantity"] == 2
    assert len(sync_event.payload_hash) == 64


def test_create_sale_rolls_back_stock_and_ledger_when_audit_fails(
    db_session,
    monkeypatch,
    cashier_user,
    category,
    product_factory,
    batch_factory,
):
    product = product_factory(category.id, name="Atomic Audit Product", sku="ATOMIC-001")
    batch = batch_factory(
        product.id,
        batch_number="ATOMIC-B1",
        quantity=5,
        expiry_offset_days=180,
    )

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(AuditService, "log", fail_audit)

    with pytest.raises(RuntimeError, match="audit unavailable"):
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

    refreshed_batch = db_session.query(ProductBatch).filter(ProductBatch.id == batch.id).one()

    assert db_session.query(Sale).count() == 0
    assert db_session.query(InventoryMovement).count() == 0
    assert db_session.query(SyncEvent).count() == 0
    assert refreshed_batch.quantity == 5
