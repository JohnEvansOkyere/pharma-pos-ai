from __future__ import annotations

from datetime import date, timedelta

from app.api.endpoints.products import list_products_catalog, receive_stock, update_product_batch
from app.api.endpoints.sales import create_sale
from app.models.activity_log import ActivityLog
from app.models.inventory_movement import InventoryMovement, InventoryMovementType
from app.models.product import Product, ProductBatch
from app.models.sale import PaymentMethod
from app.models.stock_adjustment import StockAdjustment
from app.models.sync_event import SyncEvent, SyncEventType
from app.schemas.product import ProductBatchUpdate, ReceiveStock
from app.schemas.product import ProductSearchPage
from app.schemas.sale import SaleCreate, SaleItemCreate


def test_update_product_batch_records_audit_log(db_session, manager_user, category, product_factory, batch_factory):
    product = product_factory(category.id)
    batch = batch_factory(
        product.id,
        batch_number="BATCH-001",
        quantity=20,
        expiry_offset_days=180,
    )

    updated = update_product_batch(
        product.id,
        batch.id,
        ProductBatchUpdate(location="Shelf A2", batch_number="BATCH-001A"),
        db=db_session,
        current_user=manager_user,
    )

    audit_entry = db_session.query(ActivityLog).filter(ActivityLog.entity_id == batch.id).one()

    assert updated.batch_number == "BATCH-001A"
    assert updated.location == "Shelf A2"
    assert audit_entry.action == "update_product_batch"


def test_receive_stock_creates_batch_adjustment_and_audit_log(db_session, manager_user, category, product_factory):
    product = product_factory(category.id, name="Ibuprofen", sku="IBU-400")

    result = receive_stock(
        product.id,
        ReceiveStock(
            batch_number="IBU-NEW-001",
            quantity=25,
            expiry_date=date.today() + timedelta(days=365),
            cost_price=2.5,
            selling_price=4.0,
            reason="Initial stock",
        ),
        db=db_session,
        current_user=manager_user,
    )

    refreshed_product = db_session.query(Product).filter(Product.id == product.id).one()
    saved_batch = db_session.query(ProductBatch).filter(ProductBatch.product_id == product.id).one()
    stock_adjustment = db_session.query(StockAdjustment).filter(StockAdjustment.product_id == product.id).one()
    movement = db_session.query(InventoryMovement).filter(InventoryMovement.product_id == product.id).one()
    sync_event = db_session.query(SyncEvent).filter(
        SyncEvent.event_type == SyncEventType.STOCK_RECEIVED,
        SyncEvent.aggregate_id == stock_adjustment.id,
    ).one()
    audit_entry = db_session.query(ActivityLog).filter(ActivityLog.entity_id == saved_batch.id).one()

    assert result["new_stock"] == 25
    assert refreshed_product.total_stock == 25
    assert saved_batch.batch_number == "IBU-NEW-001"
    assert stock_adjustment.quantity == 25
    assert movement.batch_id == saved_batch.id
    assert movement.movement_type == InventoryMovementType.STOCK_RECEIVED
    assert movement.quantity_delta == 25
    assert movement.stock_after == 25
    assert movement.source_document_type == "stock_adjustment"
    assert movement.source_document_id == stock_adjustment.id
    assert sync_event.payload["product_id"] == product.id
    assert sync_event.payload["batch_id"] == saved_batch.id
    assert sync_event.payload["quantity"] == 25
    assert audit_entry.action == "receive_stock"


def test_product_catalog_response_includes_wholesale_price(
    db_session,
    cashier_user,
    category,
    product_factory,
    batch_factory,
):
    product = product_factory(category.id, name="Wholesale Catalog Product", sku="WHO-CAT-1")
    product.wholesale_price = 3.0
    db_session.commit()
    batch_factory(
        product.id,
        batch_number="WHO-CAT-B1",
        quantity=8,
        expiry_offset_days=180,
    )

    response = list_products_catalog(
        q=None,
        skip=0,
        limit=25,
        category_id=None,
        is_active=True,
        db=db_session,
        current_user=cashier_user,
    )
    validated = ProductSearchPage.model_validate(response)

    assert validated.total == 1
    assert validated.items[0].wholesale_price == 3.0


def test_create_sale_depletes_batches_fefo_and_logs_audit(db_session, cashier_user, category, product_factory, batch_factory):
    product = product_factory(category.id, name="Cetirizine", sku="CET-010")
    early_batch = batch_factory(
        product.id,
        batch_number="CET-EARLY",
        quantity=2,
        expiry_offset_days=30,
    )
    late_batch = batch_factory(
        product.id,
        batch_number="CET-LATE",
        quantity=5,
        expiry_offset_days=90,
    )

    sale = create_sale(
        SaleCreate(
            items=[
                SaleItemCreate(
                    product_id=product.id,
                    quantity=4,
                    unit_price=3.5,
                    discount_amount=0.0,
                )
            ],
            payment_method=PaymentMethod.CASH,
            amount_paid=14.0,
            discount_amount=0.0,
            tax_amount=0.0,
        ),
        db=db_session,
        current_user=cashier_user,
    )

    refreshed_early_batch = db_session.query(ProductBatch).filter(ProductBatch.id == early_batch.id).one()
    refreshed_late_batch = db_session.query(ProductBatch).filter(ProductBatch.id == late_batch.id).one()
    refreshed_product = db_session.query(Product).filter(Product.id == product.id).one()
    audit_entry = db_session.query(ActivityLog).filter(ActivityLog.entity_type == "sale", ActivityLog.entity_id == sale.id).one()
    movements = db_session.query(InventoryMovement).filter(
        InventoryMovement.source_document_type == "sale",
        InventoryMovement.source_document_id == sale.id,
    ).order_by(InventoryMovement.id.asc()).all()

    assert len(sale.items) == 2
    assert sale.items[0].batch_number == "CET-EARLY"
    assert sale.items[0].quantity == 2
    assert sale.items[1].batch_number == "CET-LATE"
    assert sale.items[1].quantity == 2
    assert refreshed_early_batch.quantity == 0
    assert refreshed_late_batch.quantity == 3
    assert refreshed_product.total_stock == 3
    assert len(movements) == 2
    assert movements[0].batch_id == early_batch.id
    assert movements[0].movement_type == InventoryMovementType.SALE_DISPENSED
    assert movements[0].quantity_delta == -2
    assert movements[0].stock_after == 3
    assert movements[1].batch_id == late_batch.id
    assert movements[1].quantity_delta == -2
    assert movements[1].stock_after == 3
    assert audit_entry.action == "create_sale"
