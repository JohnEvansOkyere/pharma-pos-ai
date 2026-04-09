from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base
from app.core.security import get_password_hash
from app.models import Category, Product, ProductBatch, User
from app.models.product import DosageForm, PrescriptionStatus
from app.models.user import UserRole


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def admin_user(db_session):
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("admin-secret"),
        full_name="Admin User",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def manager_user(db_session):
    user = User(
        username="manager",
        email="manager@example.com",
        hashed_password=get_password_hash("manager-secret"),
        full_name="Manager User",
        role=UserRole.MANAGER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def cashier_user(db_session):
    user = User(
        username="cashier",
        email="cashier@example.com",
        hashed_password=get_password_hash("cashier-secret"),
        full_name="Cashier User",
        role=UserRole.CASHIER,
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
def product_factory(db_session):
    def factory(category_id: int, *, name: str = "Paracetamol", sku: str = "PARA-500") -> Product:
        product = Product(
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
        batch = ProductBatch(
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
