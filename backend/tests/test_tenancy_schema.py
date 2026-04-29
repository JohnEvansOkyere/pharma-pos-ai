from __future__ import annotations

from app.models import Branch, Device, Organization, Product
from app.models.tenancy import DeviceStatus


def test_tenant_branch_device_schema_links_to_business_records(db_session, category):
    organization = Organization(
        name="City Pharmacy Group",
        legal_name="City Pharmacy Group Ltd",
        contact_phone="0240000000",
    )
    db_session.add(organization)
    db_session.flush()

    branch = Branch(
        organization_id=organization.id,
        name="East Legon",
        code="EAST-LEGON",
        phone="0300000000",
        address="East Legon, Accra",
    )
    db_session.add(branch)
    db_session.flush()

    device = Device(
        organization_id=organization.id,
        branch_id=branch.id,
        device_uid="device-east-legon-main",
        name="Main Till",
        status=DeviceStatus.ACTIVE,
    )
    db_session.add(device)
    db_session.flush()

    product = Product(
        organization_id=organization.id,
        branch_id=branch.id,
        name="Tenant Scoped Product",
        sku="TENANT-001",
        dosage_form="TABLET",
        cost_price=2.0,
        selling_price=3.5,
        total_stock=0,
        low_stock_threshold=10,
        category_id=category.id,
        is_active=True,
    )
    db_session.add(product)
    db_session.commit()

    saved_product = db_session.query(Product).filter(Product.sku == "TENANT-001").one()
    saved_device = db_session.query(Device).filter(Device.device_uid == "device-east-legon-main").one()

    assert saved_product.organization_id == organization.id
    assert saved_product.branch_id == branch.id
    assert saved_device.organization_id == organization.id
    assert saved_device.branch_id == branch.id
    assert branch.organization_id == organization.id
