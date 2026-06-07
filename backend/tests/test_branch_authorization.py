from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.api.endpoints.customers import get_customer, list_customers
from app.api.endpoints.dashboard import (
    get_dashboard_kpis,
    get_expiring_products,
    get_fast_moving_products,
    get_financial_kpis,
    get_profit_by_category,
    get_revenue_analysis,
    get_sales_trend,
    get_slow_moving_products,
    get_staff_performance,
)
from app.api.endpoints.products import get_product, list_products, receive_stock, update_product
from app.api.endpoints.sales import get_sale, get_today_sales_summary, list_sales, void_sale
from app.api.endpoints.stock_adjustments import create_stock_adjustment
from app.api.endpoints.stock_takes import create_stock_take
from app.api.endpoints.users import create_user, list_users, update_user
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.customer import Customer
from app.models.product import DosageForm, PrescriptionStatus, Product, ProductBatch
from app.models.sale import PaymentMethod, Sale, SaleItem
from app.models.user import User, UserRole
from app.schemas.product import ProductUpdate, ReceiveStock
from app.schemas.sale import SaleActionRequest
from app.schemas.stock_adjustment import StockAdjustmentCreate
from app.schemas.stock_take import StockTakeCreate, StockTakeItemCreate
from app.schemas.user import UserCreate, UserUpdate


def _user(db, *, username: str, organization_id: int, branch_id: int, role=UserRole.CASHIER):
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("branch-secret"),
        full_name=username.replace("-", " ").title(),
        role=role,
        organization_id=organization_id,
        branch_id=branch_id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _product(db, category_id: int, *, organization_id: int, branch_id: int, sku: str, stock: int):
    product = Product(
        organization_id=organization_id,
        branch_id=branch_id,
        name=f"Product {sku}",
        sku=sku,
        dosage_form=DosageForm.TABLET,
        prescription_status=PrescriptionStatus.OTC,
        cost_price=Decimal("2.00"),
        selling_price=Decimal("3.50"),
        total_stock=stock,
        low_stock_threshold=2,
        reorder_level=5,
        reorder_quantity=10,
        category_id=category_id,
        is_active=True,
    )
    db.add(product)
    db.flush()
    batch = ProductBatch(
        organization_id=organization_id,
        branch_id=branch_id,
        product_id=product.id,
        batch_number=f"{sku}-B1",
        quantity=stock,
        expiry_date=date.today() + timedelta(days=20),
        cost_price=Decimal("2.00"),
    )
    db.add(batch)
    db.flush()
    return product, batch


def _sale(
    db,
    *,
    user_id: int,
    organization_id: int,
    branch_id: int,
    invoice: str,
    total: str,
    product: Product,
):
    sale = Sale(
        organization_id=organization_id,
        branch_id=branch_id,
        invoice_number=invoice,
        user_id=user_id,
        subtotal=Decimal(total),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal(total),
        payment_method=PaymentMethod.CASH,
        amount_paid=Decimal(total),
        change_amount=Decimal("0.00"),
    )
    db.add(sale)
    db.flush()
    db.add(
        SaleItem(
            organization_id=organization_id,
            branch_id=branch_id,
            sale_id=sale.id,
            product_id=product.id,
            product_name=product.name,
            quantity=2,
            unit_price=Decimal(total) / 2,
            discount_amount=Decimal("0.00"),
            total_price=Decimal(total),
        )
    )
    return sale


@pytest.fixture()
def branch_records(
    db_session,
    admin_user,
    category,
    assign_tenant_scope,
    monkeypatch,
):
    organization, main_branch, other_branch = assign_tenant_scope(admin_user)
    other_user = _user(
        db_session,
        username="other-branch-user",
        organization_id=organization.id,
        branch_id=other_branch.id,
    )
    main_product, main_batch = _product(
        db_session,
        category.id,
        organization_id=organization.id,
        branch_id=main_branch.id,
        sku="MAIN-SKU",
        stock=5,
    )
    other_product, other_batch = _product(
        db_session,
        category.id,
        organization_id=organization.id,
        branch_id=other_branch.id,
        sku="OTHER-SKU",
        stock=9,
    )
    main_sale = _sale(
        db_session,
        user_id=admin_user.id,
        organization_id=organization.id,
        branch_id=main_branch.id,
        invoice="INV-MAIN-BRANCH",
        total="10.00",
        product=main_product,
    )
    other_sale = _sale(
        db_session,
        user_id=other_user.id,
        organization_id=organization.id,
        branch_id=other_branch.id,
        invoice="INV-OTHER-BRANCH",
        total="99.00",
        product=other_product,
    )
    main_customer = Customer(
        organization_id=organization.id,
        branch_id=main_branch.id,
        full_name="Main Customer",
        phone="0244111100",
    )
    other_customer = Customer(
        organization_id=organization.id,
        branch_id=other_branch.id,
        full_name="Other Customer",
        phone="0244222200",
    )
    db_session.add_all([main_customer, other_customer])
    db_session.commit()
    monkeypatch.setattr(settings, "APP_MODE", "online_pos")
    return {
        "organization": organization,
        "main_branch": main_branch,
        "other_branch": other_branch,
        "other_user": other_user,
        "main_product": main_product,
        "main_batch": main_batch,
        "other_product": other_product,
        "other_batch": other_batch,
        "main_sale": main_sale,
        "other_sale": other_sale,
        "main_customer": main_customer,
        "other_customer": other_customer,
    }


def test_branch_user_cannot_read_or_reverse_another_branch_sale(
    db_session,
    admin_user,
    branch_records,
):
    assert [
        sale.id
        for sale in list_sales(
            skip=0,
            limit=50,
            start_date=None,
            end_date=None,
            db=db_session,
            current_user=admin_user,
        )
    ] == [
        branch_records["main_sale"].id
    ]

    with pytest.raises(HTTPException) as read_exc:
        get_sale(
            branch_records["other_sale"].id,
            db=db_session,
            current_user=admin_user,
        )
    with pytest.raises(HTTPException) as reverse_exc:
        void_sale(
            branch_records["other_sale"].id,
            SaleActionRequest(reason="Must not cross branches"),
            db=db_session,
            current_user=admin_user,
        )

    assert read_exc.value.status_code == 404
    assert reverse_exc.value.status_code == 404


def test_branch_sales_summaries_and_dashboard_exclude_other_branches(
    db_session,
    admin_user,
    branch_records,
):
    summary = get_today_sales_summary(db=db_session, current_user=admin_user)
    dashboard = get_dashboard_kpis(db=db_session, current_user=admin_user)

    assert summary["total_sales"] == 1
    assert summary["total_revenue"] == 10.0
    assert dashboard["total_sales_count"] == 1
    assert dashboard["total_sales_today"] == 10.0
    assert dashboard["total_products"] == 1
    assert dashboard["inventory_value"] == 10.0


def test_all_dashboard_report_families_are_branch_scoped(
    db_session,
    admin_user,
    branch_records,
):
    fast = get_fast_moving_products(db=db_session, current_user=admin_user)
    slow = get_slow_moving_products(db=db_session, current_user=admin_user)
    trend = get_sales_trend(db=db_session, current_user=admin_user)
    staff = get_staff_performance(db=db_session, current_user=admin_user)
    expiry = get_expiring_products(db=db_session, current_user=admin_user)
    profit = get_profit_by_category(db=db_session, current_user=admin_user)
    revenue = get_revenue_analysis(db=db_session, current_user=admin_user)
    financial = get_financial_kpis(db=db_session, current_user=admin_user)

    assert [row["product_id"] for row in fast] == [branch_records["main_product"].id]
    assert [row["product_id"] for row in slow] == [branch_records["main_product"].id]
    assert sum(row["total_revenue"] for row in trend) == 10.0
    assert [row["user_id"] for row in staff] == [admin_user.id]
    assert {row["product_id"] for row in expiry} == {branch_records["main_product"].id}
    assert sum(row["total_revenue"] for row in profit) == 10.0
    assert revenue["daily_revenue"] == 10.0
    assert financial["total_revenue"] == 10.0


def test_branch_user_cannot_read_or_mutate_another_branch_product(
    db_session,
    admin_user,
    branch_records,
):
    products = list_products(
        skip=0,
        limit=50,
        category_id=None,
        is_active=None,
        db=db_session,
        current_user=admin_user,
    )
    assert [product["id"] for product in products] == [branch_records["main_product"].id]

    with pytest.raises(HTTPException) as get_exc:
        get_product(
            branch_records["other_product"].id,
            db=db_session,
            current_user=admin_user,
        )
    with pytest.raises(HTTPException) as update_exc:
        update_product(
            branch_records["other_product"].id,
            ProductUpdate(name="Cross-branch update"),
            db=db_session,
            current_user=admin_user,
        )
    with pytest.raises(HTTPException) as receipt_exc:
        receive_stock(
            branch_records["other_product"].id,
            ReceiveStock(
                batch_number="OTHER-NEW",
                quantity=1,
                expiry_date=date.today() + timedelta(days=180),
                cost_price=2.0,
            ),
            db=db_session,
            current_user=admin_user,
        )

    assert get_exc.value.status_code == 404
    assert update_exc.value.status_code == 404
    assert receipt_exc.value.status_code == 404


def test_branch_user_cannot_adjust_or_count_another_branch_stock(
    db_session,
    admin_user,
    branch_records,
):
    with pytest.raises(HTTPException) as adjustment_exc:
        create_stock_adjustment(
            StockAdjustmentCreate(
                product_id=branch_records["other_product"].id,
                batch_id=branch_records["other_batch"].id,
                adjustment_type="damage",
                quantity=1,
                reason="Cross-branch attempt",
            ),
            db=db_session,
            current_user=admin_user,
        )
    with pytest.raises(HTTPException) as stock_take_exc:
        create_stock_take(
            StockTakeCreate(
                reason="Cross-branch count",
                items=[
                    StockTakeItemCreate(
                        product_id=branch_records["other_product"].id,
                        batch_id=branch_records["other_batch"].id,
                        counted_quantity=8,
                    )
                ],
            ),
            db=db_session,
            current_user=admin_user,
        )

    assert adjustment_exc.value.status_code == 404
    assert stock_take_exc.value.status_code == 404


def test_branch_user_sees_only_own_customers_and_users(
    db_session,
    admin_user,
    branch_records,
):
    customers = list_customers(
        skip=0,
        limit=50,
        is_active=None,
        db=db_session,
        current_user=admin_user,
    )
    users = list_users(db=db_session, current_user=admin_user)

    assert [customer.id for customer in customers] == [branch_records["main_customer"].id]
    assert [user.id for user in users] == [admin_user.id]

    with pytest.raises(HTTPException) as customer_exc:
        get_customer(
            branch_records["other_customer"].id,
            db=db_session,
            current_user=admin_user,
        )
    with pytest.raises(HTTPException) as user_exc:
        update_user(
            branch_records["other_user"].id,
            UserUpdate(full_name="Cross-branch update"),
            db=db_session,
            current_user=admin_user,
        )

    assert customer_exc.value.status_code == 404
    assert user_exc.value.status_code == 404


def test_created_user_inherits_operator_organization_and_branch(
    db_session,
    admin_user,
    branch_records,
):
    created = create_user(
        UserCreate(
            username="main-cashier",
            email="main-cashier@example.com",
            password="main-cashier-secret",
            full_name="Main Cashier",
            role=UserRole.CASHIER,
        ),
        db=db_session,
        current_user=admin_user,
    )

    assert created.organization_id == branch_records["organization"].id
    assert created.branch_id == branch_records["main_branch"].id


def test_organization_level_admin_can_read_all_branches(
    db_session,
    admin_user,
    branch_records,
):
    admin_user.branch_id = None
    db_session.commit()

    products = list_products(
        skip=0,
        limit=50,
        category_id=None,
        is_active=None,
        db=db_session,
        current_user=admin_user,
    )
    sales = list_sales(
        skip=0,
        limit=50,
        start_date=None,
        end_date=None,
        db=db_session,
        current_user=admin_user,
    )

    assert {product["id"] for product in products} == {
        branch_records["main_product"].id,
        branch_records["other_product"].id,
    }
    assert {sale.id for sale in sales} == {
        branch_records["main_sale"].id,
        branch_records["other_sale"].id,
    }
