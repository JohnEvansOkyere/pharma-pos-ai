from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from app.api.endpoints.products import add_product_batch, list_products_catalog, receive_stock, update_product_batch
from app.api.endpoints.sales import create_sale
from app.api.endpoints.stock_adjustments import create_stock_adjustment
from app.core.config import settings
from app.models.activity_log import ActivityLog
from app.models.customer import Customer
from app.models.inventory_movement import InventoryMovement, InventoryMovementType
from app.models.product import PrescriptionStatus, Product, ProductBatch
from app.models.sale import PaymentMethod
from app.models.stock_adjustment import StockAdjustment
from app.models.tenancy import Branch, Organization
from app.schemas.product import ProductBatchCreate, ProductBatchUpdate, ReceiveStock
from app.schemas.product import ProductSearchPage
from app.schemas.sale import SaleCreate, SaleItemCreate
from app.schemas.stock_adjustment import StockAdjustmentCreate


def _sale_request(product_id: int, *, customer_id: int | None = None) -> SaleCreate:
    return SaleCreate(
        items=[
            SaleItemCreate(
                product_id=product_id,
                quantity=1,
                unit_price=3.5,
                discount_amount=0.0,
            )
        ],
        payment_method=PaymentMethod.CASH,
        amount_paid=3.5,
        discount_amount=0.0,
        tax_amount=0.0,
        customer_id=customer_id,
    )


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


def test_receive_stock_creates_scoped_batch_adjustment_movement_and_audit(
    db_session,
    manager_user,
    category,
    product_factory,
    assign_tenant_scope,
    monkeypatch,
):
    organization, branch, _other_branch = assign_tenant_scope(manager_user)
    product = product_factory(category.id, name="Ibuprofen", sku="IBU-400")
    product.organization_id = organization.id
    product.branch_id = branch.id
    db_session.commit()
    monkeypatch.setattr(settings, "APP_MODE", "online_pos")

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
    audit_entry = db_session.query(ActivityLog).filter(ActivityLog.entity_id == saved_batch.id).one()

    assert result["new_stock"] == 25
    assert refreshed_product.total_stock == 25
    assert saved_batch.batch_number == "IBU-NEW-001"
    assert saved_batch.organization_id == organization.id
    assert saved_batch.branch_id == branch.id
    assert stock_adjustment.quantity == 25
    assert stock_adjustment.organization_id == organization.id
    assert stock_adjustment.branch_id == branch.id
    assert movement.batch_id == saved_batch.id
    assert movement.organization_id == organization.id
    assert movement.branch_id == branch.id
    assert movement.movement_type == InventoryMovementType.STOCK_RECEIVED
    assert movement.quantity_delta == 25
    assert movement.stock_after == 25
    assert movement.source_document_type == "stock_adjustment"
    assert movement.source_document_id == stock_adjustment.id
    assert audit_entry.action == "receive_stock"
    assert audit_entry.organization_id == organization.id
    assert audit_entry.branch_id == branch.id


def test_add_product_batch_scopes_batch_movement_and_audit(
    db_session,
    manager_user,
    category,
    product_factory,
    assign_tenant_scope,
    monkeypatch,
):
    organization, branch, _other_branch = assign_tenant_scope(manager_user)
    product = product_factory(category.id, name="Scoped Batch Product", sku="SCOPED-BATCH")
    product.organization_id = organization.id
    product.branch_id = branch.id
    db_session.commit()
    monkeypatch.setattr(settings, "APP_MODE", "online_pos")

    batch = add_product_batch(
        product.id,
        ProductBatchCreate(
            product_id=product.id,
            batch_number="SCOPED-B1",
            quantity=12,
            expiry_date=date.today() + timedelta(days=180),
            cost_price=2.0,
        ),
        db=db_session,
        current_user=manager_user,
    )

    movement = db_session.query(InventoryMovement).filter(
        InventoryMovement.batch_id == batch.id,
        InventoryMovement.movement_type == InventoryMovementType.INITIAL_BATCH_STOCK,
    ).one()
    audit_entry = db_session.query(ActivityLog).filter(
        ActivityLog.action == "create_product_batch",
        ActivityLog.entity_id == batch.id,
    ).one()

    assert batch.organization_id == organization.id
    assert batch.branch_id == branch.id
    assert movement.organization_id == organization.id
    assert movement.branch_id == branch.id
    assert audit_entry.organization_id == organization.id
    assert audit_entry.branch_id == branch.id


def test_manual_stock_adjustment_scopes_document_movement_and_audit(
    db_session,
    manager_user,
    category,
    product_factory,
    batch_factory,
    assign_tenant_scope,
    monkeypatch,
):
    organization, branch, _other_branch = assign_tenant_scope(manager_user)
    product = product_factory(category.id, name="Scoped Adjustment Product", sku="SCOPED-ADJ")
    batch = batch_factory(
        product.id,
        batch_number="SCOPED-ADJ-B1",
        quantity=10,
        expiry_offset_days=180,
    )
    product.organization_id = organization.id
    product.branch_id = branch.id
    batch.organization_id = organization.id
    batch.branch_id = branch.id
    db_session.commit()
    monkeypatch.setattr(settings, "APP_MODE", "online_pos")

    adjustment = create_stock_adjustment(
        StockAdjustmentCreate(
            product_id=product.id,
            batch_id=batch.id,
            adjustment_type="damage",
            quantity=2,
            reason="Damaged during handling",
        ),
        db=db_session,
        current_user=manager_user,
    )

    movement = db_session.query(InventoryMovement).filter(
        InventoryMovement.source_document_type == "stock_adjustment",
        InventoryMovement.source_document_id == adjustment.id,
    ).one()
    audit_entry = db_session.query(ActivityLog).filter(
        ActivityLog.action == "create_stock_adjustment",
        ActivityLog.entity_id == adjustment.id,
    ).one()

    assert adjustment.organization_id == organization.id
    assert adjustment.branch_id == branch.id
    assert movement.organization_id == organization.id
    assert movement.branch_id == branch.id
    assert audit_entry.organization_id == organization.id
    assert audit_entry.branch_id == branch.id


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


def test_create_sale_allows_catalog_compliance_metadata_without_checkout_evidence(
    db_session,
    cashier_user,
    category,
    product_factory,
    batch_factory,
):
    product = product_factory(category.id, name="Artemether Injection 80mg/ml", sku="ART-80")
    product.prescription_status = PrescriptionStatus.PRESCRIPTION_REQUIRED
    product.requires_id = True
    product.is_narcotic = True
    db_session.commit()
    batch_factory(
        product.id,
        batch_number="ART-B1",
        quantity=3,
        expiry_offset_days=180,
    )

    sale = create_sale(
        SaleCreate(
            items=[
                SaleItemCreate(
                    product_id=product.id,
                    quantity=1,
                    unit_price=3.5,
                    discount_amount=0.0,
                )
            ],
            payment_method=PaymentMethod.CASH,
            amount_paid=3.5,
            discount_amount=0.0,
            tax_amount=0.0,
        ),
        db=db_session,
        current_user=cashier_user,
    )

    assert sale.items[0].product_id == product.id
    assert sale.has_prescription is False
    assert sale.prescription_number is None
    assert sale.customer_id_number is None


def test_create_sale_rejects_customer_from_another_branch_before_stock_changes(
    db_session,
    cashier_user,
    category,
    product_factory,
    batch_factory,
    assign_tenant_scope,
    monkeypatch,
):
    organization, _branch, other_branch = assign_tenant_scope(cashier_user)
    customer = Customer(
        organization_id=organization.id,
        branch_id=other_branch.id,
        full_name="Other Branch Customer",
        phone="0244000001",
    )
    product = product_factory(category.id, name="Branch Test Product", sku="BRANCH-001")
    batch = batch_factory(
        product.id,
        batch_number="BRANCH-B1",
        quantity=2,
        expiry_offset_days=180,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    monkeypatch.setattr(settings, "APP_MODE", "online_pos")

    with pytest.raises(HTTPException) as exc:
        create_sale(
            _sale_request(product.id, customer_id=customer.id),
            db=db_session,
            current_user=cashier_user,
        )

    assert exc.value.status_code == 404
    db_session.refresh(batch)
    assert batch.quantity == 2


def test_create_sale_rejects_customer_from_another_organization(
    db_session,
    cashier_user,
    category,
    product_factory,
    batch_factory,
    assign_tenant_scope,
    monkeypatch,
):
    _organization, _branch, _other_branch = assign_tenant_scope(cashier_user)
    other_organization = Organization(name="Other Tenant")
    db_session.add(other_organization)
    db_session.flush()
    other_branch = Branch(
        organization_id=other_organization.id,
        name="Other Tenant Main",
        code="OTHER-TENANT",
    )
    db_session.add(other_branch)
    db_session.flush()
    customer = Customer(
        organization_id=other_organization.id,
        branch_id=other_branch.id,
        full_name="Other Tenant Customer",
        phone="0244000002",
    )
    product = product_factory(category.id, name="Tenant Test Product", sku="TENANT-001")
    batch_factory(
        product.id,
        batch_number="TENANT-B1",
        quantity=2,
        expiry_offset_days=180,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    monkeypatch.setattr(settings, "APP_MODE", "online_pos")

    with pytest.raises(HTTPException) as exc:
        create_sale(
            _sale_request(product.id, customer_id=customer.id),
            db=db_session,
            current_user=cashier_user,
        )

    assert exc.value.status_code == 404


def test_create_sale_rejects_inactive_customer(
    db_session,
    cashier_user,
    category,
    product_factory,
    batch_factory,
    assign_tenant_scope,
    monkeypatch,
):
    organization, branch, _other_branch = assign_tenant_scope(cashier_user)
    customer = Customer(
        organization_id=organization.id,
        branch_id=branch.id,
        full_name="Inactive Customer",
        phone="0244000003",
        is_active=False,
    )
    product = product_factory(category.id, name="Inactive Customer Product", sku="INACTIVE-CUST")
    batch_factory(
        product.id,
        batch_number="INACTIVE-CUST-B1",
        quantity=2,
        expiry_offset_days=180,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    monkeypatch.setattr(settings, "APP_MODE", "online_pos")

    with pytest.raises(HTTPException) as exc:
        create_sale(
            _sale_request(product.id, customer_id=customer.id),
            db=db_session,
            current_user=cashier_user,
        )

    assert exc.value.status_code == 404


def test_create_sale_links_customer_from_same_organization_and_branch(
    db_session,
    cashier_user,
    category,
    product_factory,
    batch_factory,
    assign_tenant_scope,
    monkeypatch,
):
    organization, branch, _other_branch = assign_tenant_scope(cashier_user)
    customer = Customer(
        organization_id=organization.id,
        branch_id=branch.id,
        full_name="Main Branch Customer",
        phone="0244000004",
    )
    product = product_factory(category.id, name="Valid Customer Product", sku="VALID-CUST")
    batch_factory(
        product.id,
        batch_number="VALID-CUST-B1",
        quantity=2,
        expiry_offset_days=180,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    monkeypatch.setattr(settings, "APP_MODE", "online_pos")

    sale = create_sale(
        _sale_request(product.id, customer_id=customer.id),
        db=db_session,
        current_user=cashier_user,
    )

    assert sale.customer_id == customer.id
    assert sale.organization_id == organization.id
    assert sale.branch_id == branch.id
