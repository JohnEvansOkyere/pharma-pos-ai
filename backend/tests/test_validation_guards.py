from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.endpoints.auth import login
from app.api.endpoints.products import add_product_batch, create_product
from app.api.endpoints.stock_adjustments import create_stock_adjustment
from app.models.inventory_movement import InventoryMovement, InventoryMovementType
from app.api.endpoints.sales import create_sale, refund_sale
from app.models.sale import SalePricingMode
from app.models.sale import SaleReversal
from app.models.user import User
from app.models.user import UserRole
from app.schemas.product import ProductBatchCreate, ProductCreate
from app.schemas.sale import SaleActionRequest, SaleCreate, SaleItemCreate
from app.schemas.stock_adjustment import StockAdjustmentCreate
from app.core.security import get_password_hash


def test_login_rejects_inactive_user(db_session):
    inactive_user = User(
        username="inactive-user",
        email="inactive@example.com",
        hashed_password=get_password_hash("inactive-secret"),
        full_name="Inactive User",
        role=UserRole.CASHIER,
        is_active=False,
    )
    db_session.add(inactive_user)
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        login(
            form_data=SimpleNamespace(username="inactive-user", password="inactive-secret"),
            db=db_session,
        )

    assert exc.value.status_code == 403
    assert "inactive" in exc.value.detail.lower()


def test_create_product_rejects_selling_price_below_cost(db_session, manager_user, category):
    with pytest.raises(HTTPException) as exc:
        create_product(
            ProductCreate(
                name="Invalid Pricing Product",
                sku="INV-PRICING-1",
                dosage_form="TABLET",
                cost_price=10.00,
                selling_price=9.50,
                category_id=category.id,
            ),
            db=db_session,
            current_user=manager_user,
        )

    assert exc.value.status_code == 400
    assert "lower than cost" in exc.value.detail.lower()


def test_create_product_rejects_wholesale_price_above_selling_price(db_session, manager_user, category):
    with pytest.raises(HTTPException) as exc:
        create_product(
            ProductCreate(
                name="Invalid Wholesale Product",
                sku="INV-WHOLESALE-1",
                dosage_form="TABLET",
                cost_price=70.00,
                selling_price=80.00,
                wholesale_price=90.00,
                category_id=category.id,
            ),
            db=db_session,
            current_user=manager_user,
        )

    assert exc.value.status_code == 400
    assert "wholesale price cannot be greater than selling price" in exc.value.detail.lower()


def test_add_product_batch_rejects_duplicate_batch_and_expiry(
    db_session,
    manager_user,
    category,
    product_factory,
    batch_factory,
):
    product = product_factory(category.id, name="Duplicate Batch Product", sku="DUP-BATCH-1")
    expiry_date = date.today() + timedelta(days=120)
    existing_batch = batch_factory(
        product.id,
        batch_number="DUP-001",
        quantity=10,
        expiry_offset_days=120,
    )

    with pytest.raises(HTTPException) as exc:
        add_product_batch(
            product.id,
            ProductBatchCreate(
                product_id=product.id,
                batch_number=existing_batch.batch_number,
                quantity=5,
                expiry_date=expiry_date,
                cost_price=3.00,
            ),
            db=db_session,
            current_user=manager_user,
        )

    assert exc.value.status_code == 400
    assert "same batch number and expiry date" in exc.value.detail.lower()


def test_add_product_batch_records_initial_inventory_movement(
    db_session,
    manager_user,
    category,
    product_factory,
):
    product = product_factory(category.id, name="Initial Batch Movement Product", sku="INIT-MOVE-1")

    batch = add_product_batch(
        product.id,
        ProductBatchCreate(
            product_id=product.id,
            batch_number="INIT-MOVE-B1",
            quantity=12,
            expiry_date=date.today() + timedelta(days=180),
            cost_price=3.00,
        ),
        db=db_session,
        current_user=manager_user,
    )

    movement = db_session.query(InventoryMovement).filter(
        InventoryMovement.batch_id == batch.id,
        InventoryMovement.movement_type == InventoryMovementType.INITIAL_BATCH_STOCK,
    ).one()

    assert movement.quantity_delta == 12
    assert movement.stock_after == 12
    assert movement.source_document_type == "product_batch"
    assert movement.source_document_id == batch.id


def test_stock_adjustment_records_inventory_movement(
    db_session,
    manager_user,
    category,
    product_factory,
    batch_factory,
):
    product = product_factory(category.id, name="Adjustment Movement Product", sku="ADJ-MOVE-1")
    batch = batch_factory(
        product.id,
        batch_number="ADJ-MOVE-B1",
        quantity=10,
        expiry_offset_days=180,
    )

    adjustment = create_stock_adjustment(
        StockAdjustmentCreate(
            product_id=product.id,
            batch_id=batch.id,
            adjustment_type="damage",
            quantity=3,
            reason="Damaged during handling",
        ),
        db=db_session,
        current_user=manager_user,
    )

    movement = db_session.query(InventoryMovement).filter(
        InventoryMovement.source_document_type == "stock_adjustment",
        InventoryMovement.source_document_id == adjustment.id,
    ).one()

    assert movement.batch_id == batch.id
    assert movement.movement_type == InventoryMovementType.DAMAGE_WRITE_OFF
    assert movement.quantity_delta == -3
    assert movement.stock_after == 7


def test_create_sale_rejects_inactive_product(
    db_session,
    cashier_user,
    category,
    product_factory,
    batch_factory,
):
    product = product_factory(category.id, name="Inactive Sale Product", sku="INACTIVE-SALE-1")
    product.is_active = False
    db_session.commit()
    db_session.refresh(product)

    batch_factory(
        product.id,
        batch_number="INACTIVE-B1",
        quantity=5,
        expiry_offset_days=180,
    )

    with pytest.raises(HTTPException) as exc:
        create_sale(
            SaleCreate(
                items=[SaleItemCreate(product_id=product.id, quantity=1, unit_price=3.50, discount_amount=0.0)],
                discount_amount=0.0,
                tax_amount=0.0,
                amount_paid=3.50,
            ),
            db=db_session,
            current_user=cashier_user,
        )

    assert exc.value.status_code == 400
    assert "inactive" in exc.value.detail.lower()


def test_refund_sale_rejects_second_reversal(
    db_session,
    admin_user,
    category,
    product_factory,
    batch_factory,
):
    product = product_factory(category.id, name="Refund Guard Product", sku="REFUND-GUARD-1")
    product.cost_price = Decimal("2.00")
    product.selling_price = Decimal("3.00")
    db_session.commit()
    db_session.refresh(product)

    batch_factory(
        product.id,
        batch_number="REFUND-B1",
        quantity=5,
        expiry_offset_days=180,
    )

    sale = create_sale(
        SaleCreate(
            items=[SaleItemCreate(product_id=product.id, quantity=1, unit_price=3.0, discount_amount=0.0)],
            discount_amount=0.0,
            tax_amount=0.0,
            amount_paid=3.0,
        ),
        db=db_session,
        current_user=admin_user,
    )

    refund_sale(
        sale.id,
        SaleActionRequest(reason="First refund"),
        db=db_session,
        current_user=admin_user,
    )

    with pytest.raises(HTTPException) as exc:
        refund_sale(
            sale.id,
            SaleActionRequest(reason="Second refund should fail"),
            db=db_session,
            current_user=admin_user,
        )

    assert exc.value.status_code == 400
    assert "only completed sales" in exc.value.detail.lower()
    assert db_session.query(SaleReversal).filter(SaleReversal.sale_id == sale.id).count() == 1


def test_wholesale_sale_rejects_products_without_wholesale_price(
    db_session,
    cashier_user,
    category,
    product_factory,
    batch_factory,
):
    product = product_factory(category.id, name="Retail Only", sku="RET-001")
    batch_factory(
        product.id,
        batch_number="RET-B1",
        quantity=5,
        expiry_offset_days=180,
    )

    with pytest.raises(HTTPException) as exc:
        create_sale(
            SaleCreate(
                pricing_mode=SalePricingMode.WHOLESALE,
                items=[
                    SaleItemCreate(
                        product_id=product.id,
                        quantity=1,
                        unit_price=3.50,
                        discount_amount=0.0,
                    )
                ],
                discount_amount=0.0,
                tax_amount=0.0,
                amount_paid=3.50,
            ),
            db=db_session,
            current_user=cashier_user,
        )

    assert exc.value.status_code == 400
    assert "has no wholesale price configured" in exc.value.detail.lower()
