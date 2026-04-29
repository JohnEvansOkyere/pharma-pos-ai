from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.api.dependencies.auth import require_organization_access
from app.api.endpoints.cloud_reports import (
    get_cloud_branch_sales,
    get_cloud_inventory_movement_summary,
    get_cloud_sales_summary,
    get_cloud_sync_health,
)
from app.models import Branch, Device, Organization
from app.models.cloud_projection import CloudInventoryMovementFact, CloudSaleFact
from app.models.sync_event import SyncEventType
from app.models.sync_ingestion import IngestedSyncEvent
from app.models.tenancy import DeviceStatus
from app.models.user import User, UserPermission, UserRole
from app.core.security import get_password_hash


def _tenant(db_session, *, name: str, branch_code: str):
    organization = Organization(name=name)
    db_session.add(organization)
    db_session.flush()
    branch = Branch(organization_id=organization.id, name=branch_code, code=branch_code)
    db_session.add(branch)
    db_session.flush()
    device = Device(
        organization_id=organization.id,
        branch_id=branch.id,
        device_uid=f"device-{branch_code}",
        name=f"{branch_code} Server",
        status=DeviceStatus.ACTIVE,
    )
    db_session.add(device)
    db_session.commit()
    return organization, branch, device


def _report_user(db_session, organization_id: int, *, branch_id=None, username: str = "report-user"):
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("report-secret"),
        full_name="Report User",
        role=UserRole.MANAGER,
        permissions=[UserPermission.VIEW_REPORTS.value],
        organization_id=organization_id,
        branch_id=branch_id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _ingested(db_session, organization, branch, device, *, event_id: str, sequence: int, event_type: SyncEventType):
    event = IngestedSyncEvent(
        event_id=event_id,
        organization_id=organization.id,
        branch_id=branch.id,
        source_device_id=device.id,
        local_sequence_number=sequence,
        event_type=event_type,
        aggregate_type="sale" if event_type == SyncEventType.SALE_CREATED else "stock_adjustment",
        aggregate_id=sequence,
        schema_version=1,
        payload={"id": sequence},
        payload_hash="a" * 64,
        duplicate_count=0,
    )
    db_session.add(event)
    db_session.commit()
    return event


def test_cloud_sales_summary_filters_by_organization_and_branch(db_session):
    org_a, branch_a, device_a = _tenant(db_session, name="Org A", branch_code="A")
    org_b, branch_b, device_b = _tenant(db_session, name="Org B", branch_code="B")
    event_a1 = _ingested(db_session, org_a, branch_a, device_a, event_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1", sequence=1, event_type=SyncEventType.SALE_CREATED)
    event_a2 = _ingested(db_session, org_a, branch_a, device_a, event_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2", sequence=2, event_type=SyncEventType.SALE_CREATED)
    event_b = _ingested(db_session, org_b, branch_b, device_b, event_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1", sequence=1, event_type=SyncEventType.SALE_CREATED)

    db_session.add_all(
        [
            CloudSaleFact(
                source_event_id=event_a1.id,
                organization_id=org_a.id,
                branch_id=branch_a.id,
                source_device_id=device_a.id,
                local_sale_id=1,
                invoice_number="A-1",
                total_amount=Decimal("10.00"),
                payment_method="cash",
                item_count=2,
                payload={},
            ),
            CloudSaleFact(
                source_event_id=event_a2.id,
                organization_id=org_a.id,
                branch_id=branch_a.id,
                source_device_id=device_a.id,
                local_sale_id=2,
                invoice_number="A-2",
                total_amount=Decimal("15.50"),
                payment_method="cash",
                item_count=1,
                payload={},
            ),
            CloudSaleFact(
                source_event_id=event_b.id,
                organization_id=org_b.id,
                branch_id=branch_b.id,
                source_device_id=device_b.id,
                local_sale_id=1,
                invoice_number="B-1",
                total_amount=Decimal("99.00"),
                payment_method="cash",
                item_count=5,
                payload={},
            ),
        ]
    )
    db_session.commit()
    report_user = _report_user(db_session, org_a.id)

    summary = get_cloud_sales_summary(organization_id=org_a.id, branch_id=branch_a.id, db=db_session, current_user=report_user)
    branch_rows = get_cloud_branch_sales(organization_id=org_a.id, db=db_session, current_user=report_user)

    assert summary.sales_count == 2
    assert summary.total_revenue == 25.5
    assert summary.total_items == 3
    assert len(branch_rows) == 1
    assert branch_rows[0].branch_id == branch_a.id
    assert branch_rows[0].sales_count == 2


def test_cloud_inventory_movement_summary(db_session):
    org, branch, device = _tenant(db_session, name="Movement Org", branch_code="MOV")
    event = _ingested(db_session, org, branch, device, event_id="cccccccc-cccc-cccc-cccc-ccccccccccc1", sequence=1, event_type=SyncEventType.STOCK_ADJUSTED)
    db_session.add_all(
        [
            CloudInventoryMovementFact(
                source_event_id=event.id,
                line_number=1,
                organization_id=org.id,
                branch_id=branch.id,
                source_device_id=device.id,
                event_type=SyncEventType.STOCK_ADJUSTED.value,
                local_product_id=1,
                local_batch_id=1,
                quantity_delta=10,
                stock_after=20,
                payload={},
            ),
            CloudInventoryMovementFact(
                source_event_id=event.id,
                line_number=2,
                organization_id=org.id,
                branch_id=branch.id,
                source_device_id=device.id,
                event_type=SyncEventType.STOCK_ADJUSTED.value,
                local_product_id=1,
                local_batch_id=2,
                quantity_delta=-3,
                stock_after=17,
                payload={},
            ),
        ]
    )
    db_session.commit()
    report_user = _report_user(db_session, org.id)

    summary = get_cloud_inventory_movement_summary(organization_id=org.id, branch_id=branch.id, db=db_session, current_user=report_user)

    assert summary.movement_count == 2
    assert summary.total_positive_quantity == 10
    assert summary.total_negative_quantity == -3
    assert summary.net_quantity_delta == 7


def test_cloud_sync_health_counts_ingested_projection_and_duplicates(db_session):
    org, branch, device = _tenant(db_session, name="Health Org", branch_code="HLTH")
    event_one = _ingested(db_session, org, branch, device, event_id="dddddddd-dddd-dddd-dddd-ddddddddddd1", sequence=1, event_type=SyncEventType.SALE_CREATED)
    event_two = _ingested(db_session, org, branch, device, event_id="dddddddd-dddd-dddd-dddd-ddddddddddd2", sequence=2, event_type=SyncEventType.STOCK_RECEIVED)
    event_one.duplicate_count = 2
    event_one.projected_at = event_one.received_at
    event_two.projection_error = "bad payload"
    db_session.commit()
    report_user = _report_user(db_session, org.id)

    health = get_cloud_sync_health(organization_id=org.id, branch_id=branch.id, db=db_session, current_user=report_user)

    assert health.ingested_event_count == 2
    assert health.projected_event_count == 1
    assert health.projection_failed_count == 1
    assert health.duplicate_delivery_count == 2
    assert health.last_received_at is not None
    assert health.last_projected_at is not None


def test_cloud_report_rejects_cross_organization_access(db_session):
    org_a, _branch_a, _device_a = _tenant(db_session, name="Tenant A", branch_code="TA")
    org_b, _branch_b, _device_b = _tenant(db_session, name="Tenant B", branch_code="TB")
    report_user = _report_user(db_session, org_a.id)

    with pytest.raises(HTTPException) as exc:
        require_organization_access(organization_id=org_b.id, current_user=report_user)

    assert exc.value.status_code == 403
    assert "Organization access denied" in exc.value.detail


def test_cloud_report_rejects_cross_branch_access(db_session):
    org = Organization(name="Branch Tenant")
    db_session.add(org)
    db_session.flush()
    branch_a = Branch(organization_id=org.id, name="Branch A", code="BA")
    branch_b = Branch(organization_id=org.id, name="Branch B", code="BB")
    db_session.add_all([branch_a, branch_b])
    db_session.commit()
    report_user = _report_user(db_session, org.id, branch_id=branch_a.id, username="branch-report-user")

    with pytest.raises(HTTPException) as exc:
        require_organization_access(organization_id=org.id, branch_id=branch_b.id, current_user=report_user)

    assert exc.value.status_code == 403
    assert "Branch access denied" in exc.value.detail


def test_branch_scoped_report_user_only_sees_assigned_branch(db_session):
    org = Organization(name="Scoped Tenant")
    db_session.add(org)
    db_session.flush()
    branch_a = Branch(organization_id=org.id, name="Branch A", code="SA")
    branch_b = Branch(organization_id=org.id, name="Branch B", code="SB")
    db_session.add_all([branch_a, branch_b])
    db_session.flush()
    device_a = Device(
        organization_id=org.id,
        branch_id=branch_a.id,
        device_uid="scoped-device-a",
        name="Scoped Device A",
        status=DeviceStatus.ACTIVE,
    )
    device_b = Device(
        organization_id=org.id,
        branch_id=branch_b.id,
        device_uid="scoped-device-b",
        name="Scoped Device B",
        status=DeviceStatus.ACTIVE,
    )
    db_session.add_all([device_a, device_b])
    db_session.commit()
    event_a = _ingested(db_session, org, branch_a, device_a, event_id="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee1", sequence=1, event_type=SyncEventType.SALE_CREATED)
    event_b = _ingested(db_session, org, branch_b, device_b, event_id="ffffffff-ffff-ffff-ffff-fffffffffff1", sequence=1, event_type=SyncEventType.SALE_CREATED)
    db_session.add_all(
        [
            CloudSaleFact(
                source_event_id=event_a.id,
                organization_id=org.id,
                branch_id=branch_a.id,
                source_device_id=device_a.id,
                local_sale_id=1,
                invoice_number="SA-1",
                total_amount=Decimal("30.00"),
                payment_method="cash",
                item_count=3,
                payload={},
            ),
            CloudSaleFact(
                source_event_id=event_b.id,
                organization_id=org.id,
                branch_id=branch_b.id,
                source_device_id=device_b.id,
                local_sale_id=1,
                invoice_number="SB-1",
                total_amount=Decimal("80.00"),
                payment_method="cash",
                item_count=8,
                payload={},
            ),
        ]
    )
    db_session.commit()
    report_user = _report_user(db_session, org.id, branch_id=branch_a.id, username="scoped-report-user")

    summary = get_cloud_sales_summary(organization_id=org.id, db=db_session, current_user=report_user)
    branch_rows = get_cloud_branch_sales(organization_id=org.id, db=db_session, current_user=report_user)

    assert summary.branch_id == branch_a.id
    assert summary.sales_count == 1
    assert summary.total_revenue == 30.0
    assert len(branch_rows) == 1
    assert branch_rows[0].branch_id == branch_a.id


def test_cloud_report_allows_platform_admin_access(db_session):
    org, _branch, _device = _tenant(db_session, name="Platform Tenant", branch_code="PT")
    platform_admin = User(
        username="platform-admin",
        email="platform-admin@example.com",
        hashed_password=get_password_hash("admin-secret"),
        full_name="Platform Admin",
        role=UserRole.ADMIN,
        permissions=[UserPermission.VIEW_REPORTS.value],
        organization_id=None,
        is_active=True,
    )
    db_session.add(platform_admin)
    db_session.commit()

    assert require_organization_access(organization_id=org.id, current_user=platform_admin) == platform_admin
