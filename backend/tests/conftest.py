from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base
from app.core.config import settings
from app.core.security import get_password_hash
from app.models import Branch, Category, Organization, Product, ProductBatch, User
from app.models.product import DosageForm, PrescriptionStatus
from app.models.user import UserRole

_TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
_IS_POSTGRES = _TEST_DB_URL.startswith("postgresql")
_TEST_DEPLOYMENT_PROFILE = os.getenv(
    "TEST_POS_DEPLOYMENT_PROFILE",
    "offline",
).strip().lower()

if _TEST_DEPLOYMENT_PROFILE not in {"offline", "hosted"}:
    raise RuntimeError(
        "TEST_POS_DEPLOYMENT_PROFILE must be either 'offline' or 'hosted'"
    )


@pytest.fixture(autouse=True)
def _pin_operational_test_profile(monkeypatch):
    """Keep tests independent from developer .env files and shell settings."""
    monkeypatch.setattr(settings, "APP_MODE", "operational_pos")
    monkeypatch.setattr(
        settings,
        "POS_DEPLOYMENT_PROFILE",
        _TEST_DEPLOYMENT_PROFILE,
    )


@pytest.fixture(scope="session")
def _engine():
    if _IS_POSTGRES:
        engine = create_engine(_TEST_DB_URL)
    else:
        # StaticPool keeps the same in-memory connection alive for the whole session
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(_engine):
    session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        # Wipe all rows between tests so each test starts with a clean slate
        with _engine.begin() as conn:
            if _IS_POSTGRES:
                tables = ", ".join(
                    f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables)
                )
                conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
            else:
                for table in reversed(Base.metadata.sorted_tables):
                    conn.execute(table.delete())


@pytest.fixture()
def tenant_scope(db_session):
    if _TEST_DEPLOYMENT_PROFILE != "hosted":
        return None

    organization = Organization(name="Hosted Test Pharmacy")
    db_session.add(organization)
    db_session.flush()
    branch = Branch(
        organization_id=organization.id,
        name="Main Branch",
        code="MAIN",
    )
    other_branch = Branch(
        organization_id=organization.id,
        name="Other Branch",
        code="OTHER",
    )
    db_session.add_all([branch, other_branch])
    db_session.flush()
    return organization, branch, other_branch


def _tenant_ids(tenant_scope):
    if tenant_scope is None:
        return None, None
    organization, branch, _other_branch = tenant_scope
    return organization.id, branch.id


@pytest.fixture()
def admin_user(db_session, tenant_scope):
    organization_id, branch_id = _tenant_ids(tenant_scope)
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("admin-secret"),
        full_name="Admin User",
        role=UserRole.ADMIN,
        organization_id=organization_id,
        branch_id=branch_id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def manager_user(db_session, tenant_scope):
    organization_id, branch_id = _tenant_ids(tenant_scope)
    user = User(
        username="manager",
        email="manager@example.com",
        hashed_password=get_password_hash("manager-secret"),
        full_name="Manager User",
        role=UserRole.MANAGER,
        organization_id=organization_id,
        branch_id=branch_id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def cashier_user(db_session, tenant_scope):
    organization_id, branch_id = _tenant_ids(tenant_scope)
    user = User(
        username="cashier",
        email="cashier@example.com",
        hashed_password=get_password_hash("cashier-secret"),
        full_name="Cashier User",
        role=UserRole.CASHIER,
        organization_id=organization_id,
        branch_id=branch_id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def category(db_session):
    category = Category(name="Analgesics", description="Pain medication")
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


@pytest.fixture()
def assign_tenant_scope(db_session, tenant_scope):
    def assign(user: User):
        if tenant_scope is None:
            organization = Organization(name=f"Tenant Pharmacy {user.username}")
            db_session.add(organization)
            db_session.flush()
            branch = Branch(
                organization_id=organization.id,
                name="Main Branch",
                code="MAIN",
            )
            other_branch = Branch(
                organization_id=organization.id,
                name="Other Branch",
                code="OTHER",
            )
            db_session.add_all([branch, other_branch])
            db_session.flush()
        else:
            organization, branch, other_branch = tenant_scope

        user.organization_id = organization.id
        user.branch_id = branch.id
        db_session.commit()
        return organization, branch, other_branch

    return assign


@pytest.fixture()
def product_factory(db_session, tenant_scope):
    organization_id, branch_id = _tenant_ids(tenant_scope)

    def factory(category_id: int, *, name: str = "Paracetamol", sku: str = "PARA-500") -> Product:
        product = Product(
            organization_id=organization_id,
            branch_id=branch_id,
            name=name,
            sku=sku,
            dosage_form=DosageForm.TABLET,
            prescription_status=PrescriptionStatus.OTC,
            cost_price=2.0,
            selling_price=3.5,
            total_stock=0,
            low_stock_threshold=10,
            reorder_level=20,
            reorder_quantity=100,
            category_id=category_id,
            is_active=True,
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        return product

    return factory


@pytest.fixture()
def batch_factory(db_session):
    def factory(
        product_id: int,
        *,
        batch_number: str,
        quantity: int,
        expiry_offset_days: int,
    ) -> ProductBatch:
        product = db_session.query(Product).filter(Product.id == product_id).one()
        batch = ProductBatch(
            organization_id=product.organization_id,
            branch_id=product.branch_id,
            product_id=product_id,
            batch_number=batch_number,
            quantity=quantity,
            expiry_date=date.today() + timedelta(days=expiry_offset_days),
            cost_price=2.0,
        )
        db_session.add(batch)
        db_session.commit()
        db_session.refresh(batch)
        return batch

    return factory
