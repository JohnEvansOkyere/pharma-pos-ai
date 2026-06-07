from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.api.dependencies.auth import require_organization_access
from app.api.endpoints.cloud_reports import (
    acknowledge_cloud_reconciliation_issue,
    get_cloud_branch_sales,
    get_cloud_dead_stock,
    get_cloud_expiry_risk,
    get_cloud_inventory_movement_summary,
    get_cloud_low_stock,
    get_cloud_profit_summary,
    get_cloud_reconciliation,
    get_cloud_revenue_comparison,
    get_cloud_sales_summary,
    get_cloud_stock_value,
    get_cloud_stockout_impact,
    get_cloud_stock_risk_summary,
    get_cloud_stock_velocity,
    get_cloud_sync_health,
    repair_cloud_reconciliation_issue,
    resolve_cloud_reconciliation_issue,
)
from app.models import Branch, Device, Organization
from app.models.activity_log import ActivityLog
from app.models.cloud_projection import (
    CloudBatchSnapshot,
    CloudInventoryMovementFact,
    CloudProductSnapshot,
    CloudSaleFact,
)
from app.models.sync_event import SyncEventType
from app.models.sync_ingestion import IngestedSyncEvent
from app.models.tenancy import DeviceStatus
from app.models.user import User, UserPermission, UserRole
from app.core.security import get_password_hash
from app.schemas.cloud_reports import CloudReconciliationIssueActionRequest, CloudReconciliationRepairRequest
from app.services.sync_identity_service import build_aggregate_uid


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


def _report_user(
    db_session,
    organization_id: int,
    *,
    branch_id=None,
    username: str = "report-user",
    role: UserRole = UserRole.MANAGER,
):
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("report-secret"),
        full_name="Report User",
        role=role,
        permissions=[UserPermission.VIEW_REPORTS.value],
        organization_id=organization_id,
        branch_id=branch_id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _ingested(db_session, organization, branch, device, *, event_id: str, sequence: int, event_type: SyncEventType):
    aggregate_type = "sale" if event_type == SyncEventType.SALE_CREATED else "stock_adjustment"
    event = IngestedSyncEvent(
        event_id=event_id,
        organization_id=organization.id,
        branch_id=branch.id,
        source_device_id=device.id,
        deployment_uid=device.deployment_uid,
        local_sequence_number=sequence,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=sequence,
        aggregate_uid=build_aggregate_uid(device.deployment_uid, aggregate_type, sequence),
        schema_version=1,
        payload={"id": sequence},
        payload_hash="a" * 64,
        duplicate_count=0,
    )
    db_session.add(event)
    db_session.commit()
    return event


def _seed_reconciliation_issue(db_session):
    org, branch, device = _tenant(db_session, name="Reconcile Workflow Org", branch_code="RWK")
    event = _ingested(
        db_session,
        org,
        branch,
        device,
        event_id="99999999-9999-9999-9999-999999999991",
        sequence=1,
        event_type=SyncEventType.PRODUCT_CREATED,
    )
    db_session.add(
        CloudProductSnapshot(
            organization_id=org.id,
            branch_id=branch.id,
            local_product_id=10,
            name="Workflow Mismatch Tabs",
            sku="WMM-10",
            total_stock=-2,
            low_stock_threshold=2,
            is_active=True,
            last_source_event_id=event.id,
            payload={},
        )
    )
    db_session.commit()
    user = _report_user(db_session, org.id, branch_id=branch.id, username="reconcile-workflow-user")
    return org, branch, user


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
    assert summary.average_transaction_value == 12.75
    assert len(branch_rows) == 1
    assert branch_rows[0].branch_id == branch_a.id
    assert branch_rows[0].sales_count == 2


def test_cloud_sales_summary_filters_by_sale_occurred_at(db_session):
    org, branch, device = _tenant(db_session, name="Occurred Org", branch_code="OCC")
    event = _ingested(
        db_session,
        org,
        branch,
        device,
        event_id="cccccccc-cccc-cccc-cccc-ccccccccccc1",
        sequence=1,
        event_type=SyncEventType.SALE_CREATED,
    )
    db_session.add(
        CloudSaleFact(
            source_event_id=event.id,
            organization_id=org.id,
            branch_id=branch.id,
            source_device_id=device.id,
            local_sale_id=1,
            invoice_number="OCC-1",
            total_amount=Decimal("25.00"),
            payment_method="cash",
            item_count=2,
            payload={},
            occurred_at=datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
            created_at=datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc),
        )
    )
    db_session.commit()
    report_user = _report_user(db_session, org.id)

    summary = get_cloud_sales_summary(
        organization_id=org.id,
        start_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 5, 18, 23, 59, tzinfo=timezone.utc),
        db=db_session,
        current_user=report_user,
    )

    assert summary.sales_count == 1
    assert summary.total_revenue == 25.0


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


def test_cloud_stock_risk_reports_are_tenant_and_branch_scoped(db_session):
    org, branch, device = _tenant(db_session, name="Risk Org", branch_code="RISK")
    other_org, other_branch, other_device = _tenant(db_session, name="Other Risk Org", branch_code="ORISK")
    event = _ingested(db_session, org, branch, device, event_id="99999999-9999-9999-9999-999999999991", sequence=1, event_type=SyncEventType.PRODUCT_CREATED)
    other_event = _ingested(db_session, other_org, other_branch, other_device, event_id="99999999-9999-9999-9999-999999999992", sequence=1, event_type=SyncEventType.PRODUCT_CREATED)
    db_session.add_all(
        [
            CloudProductSnapshot(
                organization_id=org.id,
                branch_id=branch.id,
                local_product_id=1,
                name="Low Stock Tabs",
                sku="LOW-1",
                total_stock=3,
                low_stock_threshold=5,
                reorder_level=10,
                cost_price=Decimal("2.00"),
                selling_price=Decimal("4.00"),
                is_active=True,
                last_source_event_id=event.id,
                payload={},
            ),
            CloudProductSnapshot(
                organization_id=org.id,
                branch_id=branch.id,
                local_product_id=2,
                name="Out Stock Syrup",
                sku="OUT-1",
                total_stock=0,
                low_stock_threshold=5,
                reorder_level=12,
                cost_price=Decimal("3.00"),
                selling_price=Decimal("6.00"),
                is_active=True,
                last_source_event_id=event.id,
                payload={},
            ),
            CloudProductSnapshot(
                organization_id=other_org.id,
                branch_id=other_branch.id,
                local_product_id=1,
                name="Other Low Stock",
                sku="OTHER-1",
                total_stock=0,
                low_stock_threshold=10,
                is_active=True,
                last_source_event_id=other_event.id,
                payload={},
            ),
            CloudBatchSnapshot(
                organization_id=org.id,
                branch_id=branch.id,
                local_product_id=1,
                local_batch_id=10,
                batch_number="EXP-1",
                quantity=3,
                expiry_date=date.today() + timedelta(days=20),
                cost_price=Decimal("2.00"),
                is_quarantined=False,
                last_source_event_id=event.id,
                payload={},
            ),
            CloudBatchSnapshot(
                organization_id=org.id,
                branch_id=branch.id,
                local_product_id=2,
                local_batch_id=11,
                batch_number="OLD-1",
                quantity=4,
                expiry_date=date.today() - timedelta(days=1),
                cost_price=Decimal("3.00"),
                is_quarantined=False,
                last_source_event_id=event.id,
                payload={},
            ),
        ]
    )
    db_session.commit()
    report_user = _report_user(db_session, org.id, branch_id=branch.id, username="risk-report-user")

    summary = get_cloud_stock_risk_summary(
        organization_id=org.id,
        expiry_warning_days=90,
        db=db_session,
        current_user=report_user,
    )
    low_stock = get_cloud_low_stock(
        organization_id=org.id,
        limit=50,
        db=db_session,
        current_user=report_user,
    )
    expiry_risk = get_cloud_expiry_risk(
        organization_id=org.id,
        days=30,
        limit=50,
        db=db_session,
        current_user=report_user,
    )

    assert summary.branch_id == branch.id
    assert summary.low_stock_count == 1
    assert summary.out_of_stock_count == 1
    assert summary.near_expiry_batch_count == 1
    assert summary.expired_batch_count == 1
    assert summary.value_at_risk == 18.0
    assert [item.product_id for item in low_stock] == [2, 1]
    assert low_stock[0].status == "out_of_stock"
    assert {item.batch_id for item in expiry_risk} == {10, 11}
    assert any(item.status == "expired" for item in expiry_risk)


def test_cloud_stock_velocity_uses_sale_movements_for_days_remaining(db_session):
    org, branch, device = _tenant(db_session, name="Velocity Org", branch_code="VEL")
    sale_event = _ingested(
        db_session,
        org,
        branch,
        device,
        event_id="77777777-7777-7777-7777-777777777771",
        sequence=1,
        event_type=SyncEventType.SALE_CREATED,
    )
    adjustment_event = _ingested(
        db_session,
        org,
        branch,
        device,
        event_id="77777777-7777-7777-7777-777777777772",
        sequence=2,
        event_type=SyncEventType.STOCK_ADJUSTED,
    )
    db_session.add_all(
        [
            CloudProductSnapshot(
                organization_id=org.id,
                branch_id=branch.id,
                local_product_id=1,
                name="Fast Moving Tabs",
                sku="FAST-1",
                total_stock=5,
                low_stock_threshold=10,
                reorder_level=20,
                is_active=True,
                last_source_event_id=sale_event.id,
                payload={},
            ),
            CloudProductSnapshot(
                organization_id=org.id,
                branch_id=branch.id,
                local_product_id=2,
                name="No Movement Syrup",
                sku="ZERO-1",
                total_stock=20,
                low_stock_threshold=5,
                is_active=True,
                last_source_event_id=sale_event.id,
                payload={},
            ),
            CloudInventoryMovementFact(
                source_event_id=sale_event.id,
                line_number=1,
                organization_id=org.id,
                branch_id=branch.id,
                source_device_id=device.id,
                event_type=SyncEventType.SALE_CREATED.value,
                local_product_id=1,
                local_batch_id=10,
                quantity_delta=-8,
                stock_after=None,
                payload={},
                occurred_at=datetime.now(timezone.utc) - timedelta(days=1),
            ),
            CloudInventoryMovementFact(
                source_event_id=sale_event.id,
                line_number=2,
                organization_id=org.id,
                branch_id=branch.id,
                source_device_id=device.id,
                event_type=SyncEventType.SALE_CREATED.value,
                local_product_id=1,
                local_batch_id=11,
                quantity_delta=-6,
                stock_after=None,
                payload={},
                occurred_at=datetime.now(timezone.utc) - timedelta(days=2),
            ),
            CloudInventoryMovementFact(
                source_event_id=adjustment_event.id,
                line_number=1,
                organization_id=org.id,
                branch_id=branch.id,
                source_device_id=device.id,
                event_type=SyncEventType.STOCK_ADJUSTED.value,
                local_product_id=1,
                local_batch_id=10,
                quantity_delta=-100,
                stock_after=None,
                payload={},
                occurred_at=datetime.now(timezone.utc) - timedelta(days=1),
            ),
        ]
    )
    db_session.commit()
    report_user = _report_user(db_session, org.id)

    velocity = get_cloud_stock_velocity(
        organization_id=org.id,
        period_days=7,
        limit=10,
        db=db_session,
        current_user=report_user,
    )

    assert [item.product_id for item in velocity] == [1, 2]
    fast = velocity[0]
    zero = velocity[1]
    assert fast.units_sold == 14
    assert fast.movement_count == 2
    assert fast.average_daily_units_sold == 2.0
    assert fast.days_of_stock_remaining == 2.5
    assert fast.estimated_stockout_date is not None
    assert fast.units_needed == 15
    assert fast.status == "critical"
    assert fast.confidence == "low"
    assert zero.units_sold == 0
    assert zero.days_of_stock_remaining is None
    assert zero.status == "no_velocity"
    assert zero.confidence == "none"


def test_cloud_profit_stock_value_and_stockout_impact_metrics(db_session):
    org, branch, device = _tenant(db_session, name="CEO KPI Org", branch_code="CEO")
    sale_event = _ingested(
        db_session,
        org,
        branch,
        device,
        event_id="34343434-3434-3434-3434-343434343431",
        sequence=1,
        event_type=SyncEventType.SALE_CREATED,
    )
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            CloudSaleFact(
                source_event_id=sale_event.id,
                organization_id=org.id,
                branch_id=branch.id,
                source_device_id=device.id,
                local_sale_id=1,
                invoice_number="CEO-1",
                total_amount=Decimal("100.00"),
                payment_method="cash",
                item_count=5,
                payload={},
                occurred_at=now - timedelta(days=1),
            ),
            CloudProductSnapshot(
                organization_id=org.id,
                branch_id=branch.id,
                local_product_id=1,
                name="Margin Tablets",
                sku="MARGIN-1",
                total_stock=10,
                low_stock_threshold=2,
                cost_price=Decimal("4.00"),
                selling_price=Decimal("10.00"),
                is_active=True,
                last_source_event_id=sale_event.id,
                payload={},
            ),
            CloudProductSnapshot(
                organization_id=org.id,
                branch_id=branch.id,
                local_product_id=2,
                name="Stockout Syrup",
                sku="OUT-2",
                total_stock=0,
                low_stock_threshold=5,
                cost_price=Decimal("3.00"),
                selling_price=Decimal("12.00"),
                is_active=True,
                last_source_event_id=sale_event.id,
                payload={},
            ),
            CloudInventoryMovementFact(
                source_event_id=sale_event.id,
                line_number=1,
                organization_id=org.id,
                branch_id=branch.id,
                source_device_id=device.id,
                event_type=SyncEventType.SALE_CREATED.value,
                local_product_id=1,
                local_batch_id=10,
                quantity_delta=-5,
                stock_after=None,
                payload={},
                occurred_at=now - timedelta(days=1),
            ),
            CloudInventoryMovementFact(
                source_event_id=sale_event.id,
                line_number=2,
                organization_id=org.id,
                branch_id=branch.id,
                source_device_id=device.id,
                event_type=SyncEventType.SALE_CREATED.value,
                local_product_id=2,
                local_batch_id=11,
                quantity_delta=-6,
                stock_after=None,
                payload={},
                occurred_at=now - timedelta(days=2),
            ),
        ]
    )
    db_session.commit()
    report_user = _report_user(db_session, org.id)

    profit = get_cloud_profit_summary(
        organization_id=org.id,
        start_at=now - timedelta(days=7),
        end_at=now,
        db=db_session,
        current_user=report_user,
    )
    stock_value = get_cloud_stock_value(
        organization_id=org.id,
        db=db_session,
        current_user=report_user,
    )
    impact = get_cloud_stockout_impact(
        organization_id=org.id,
        period_days=3,
        limit=10,
        db=db_session,
        current_user=report_user,
    )

    assert profit.total_revenue == 100.0
    assert profit.estimated_cost == 38.0
    assert profit.estimated_gross_profit == 62.0
    assert profit.gross_margin_percent == 62.0
    assert stock_value.total_cost_value == 40.0
    assert stock_value.total_retail_value == 100.0
    assert impact.stockout_product_count == 1
    assert impact.total_daily_revenue_at_risk == 24.0
    assert impact.items[0].product_name == "Stockout Syrup"


def test_cloud_stock_velocity_respects_branch_scope_and_can_hide_stable_items(db_session):
    org = Organization(name="Velocity Scoped Org")
    db_session.add(org)
    db_session.flush()
    branch_a = Branch(organization_id=org.id, name="Velocity A", code="VA")
    branch_b = Branch(organization_id=org.id, name="Velocity B", code="VB")
    db_session.add_all([branch_a, branch_b])
    db_session.flush()
    device_a = Device(organization_id=org.id, branch_id=branch_a.id, device_uid="velocity-a", name="Velocity A", status=DeviceStatus.ACTIVE)
    device_b = Device(organization_id=org.id, branch_id=branch_b.id, device_uid="velocity-b", name="Velocity B", status=DeviceStatus.ACTIVE)
    db_session.add_all([device_a, device_b])
    db_session.commit()
    event_a = _ingested(db_session, org, branch_a, device_a, event_id="77777777-7777-7777-7777-777777777773", sequence=1, event_type=SyncEventType.SALE_CREATED)
    event_b = _ingested(db_session, org, branch_b, device_b, event_id="77777777-7777-7777-7777-777777777774", sequence=1, event_type=SyncEventType.SALE_CREATED)
    db_session.add_all(
        [
            CloudProductSnapshot(
                organization_id=org.id,
                branch_id=branch_a.id,
                local_product_id=1,
                name="Branch A Stable",
                sku="VA-STABLE",
                total_stock=200,
                low_stock_threshold=5,
                is_active=True,
                last_source_event_id=event_a.id,
                payload={},
            ),
            CloudProductSnapshot(
                organization_id=org.id,
                branch_id=branch_b.id,
                local_product_id=1,
                name="Branch B Critical",
                sku="VB-CRIT",
                total_stock=1,
                low_stock_threshold=5,
                is_active=True,
                last_source_event_id=event_b.id,
                payload={},
            ),
            CloudInventoryMovementFact(
                source_event_id=event_a.id,
                line_number=1,
                organization_id=org.id,
                branch_id=branch_a.id,
                source_device_id=device_a.id,
                event_type=SyncEventType.SALE_CREATED.value,
                local_product_id=1,
                local_batch_id=1,
                quantity_delta=-10,
                stock_after=None,
                payload={},
                occurred_at=datetime.now(timezone.utc) - timedelta(days=1),
            ),
            CloudInventoryMovementFact(
                source_event_id=event_b.id,
                line_number=1,
                organization_id=org.id,
                branch_id=branch_b.id,
                source_device_id=device_b.id,
                event_type=SyncEventType.SALE_CREATED.value,
                local_product_id=1,
                local_batch_id=1,
                quantity_delta=-10,
                stock_after=None,
                payload={},
                occurred_at=datetime.now(timezone.utc) - timedelta(days=1),
            ),
        ]
    )
    db_session.commit()
    report_user = _report_user(db_session, org.id, branch_id=branch_b.id, username="velocity-branch-user")

    velocity = get_cloud_stock_velocity(
        organization_id=org.id,
        period_days=10,
        limit=10,
        include_stable=False,
        db=db_session,
        current_user=report_user,
    )

    assert len(velocity) == 1
    assert velocity[0].branch_id == branch_b.id
    assert velocity[0].product_name == "Branch B Critical"
    assert velocity[0].status == "critical"


def test_cloud_revenue_comparison_flags_branch_drops_and_growth(db_session):
    org = Organization(name="Trend Org")
    db_session.add(org)
    db_session.flush()
    branch_drop = Branch(organization_id=org.id, name="Drop Branch", code="DROP")
    branch_growth = Branch(organization_id=org.id, name="Growth Branch", code="GROW")
    db_session.add_all([branch_drop, branch_growth])
    db_session.flush()
    device_drop = Device(organization_id=org.id, branch_id=branch_drop.id, device_uid="trend-drop", name="Trend Drop", status=DeviceStatus.ACTIVE)
    device_growth = Device(organization_id=org.id, branch_id=branch_growth.id, device_uid="trend-growth", name="Trend Growth", status=DeviceStatus.ACTIVE)
    db_session.add_all([device_drop, device_growth])
    db_session.commit()
    drop_previous_event = _ingested(db_session, org, branch_drop, device_drop, event_id="12121212-1212-1212-1212-121212121211", sequence=1, event_type=SyncEventType.SALE_CREATED)
    drop_current_event = _ingested(db_session, org, branch_drop, device_drop, event_id="12121212-1212-1212-1212-121212121212", sequence=2, event_type=SyncEventType.SALE_CREATED)
    growth_previous_event = _ingested(db_session, org, branch_growth, device_growth, event_id="12121212-1212-1212-1212-121212121213", sequence=1, event_type=SyncEventType.SALE_CREATED)
    growth_current_event = _ingested(db_session, org, branch_growth, device_growth, event_id="12121212-1212-1212-1212-121212121214", sequence=2, event_type=SyncEventType.SALE_CREATED)
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            CloudSaleFact(
                source_event_id=drop_previous_event.id,
                organization_id=org.id,
                branch_id=branch_drop.id,
                source_device_id=device_drop.id,
                local_sale_id=1,
                invoice_number="DROP-PREV",
                total_amount=Decimal("100.00"),
                payment_method="cash",
                item_count=1,
                payload={},
                occurred_at=now - timedelta(days=10),
            ),
            CloudSaleFact(
                source_event_id=drop_current_event.id,
                organization_id=org.id,
                branch_id=branch_drop.id,
                source_device_id=device_drop.id,
                local_sale_id=2,
                invoice_number="DROP-CUR",
                total_amount=Decimal("10.00"),
                payment_method="cash",
                item_count=1,
                payload={},
                occurred_at=now - timedelta(days=2),
            ),
            CloudSaleFact(
                source_event_id=growth_previous_event.id,
                organization_id=org.id,
                branch_id=branch_growth.id,
                source_device_id=device_growth.id,
                local_sale_id=1,
                invoice_number="GROW-PREV",
                total_amount=Decimal("20.00"),
                payment_method="cash",
                item_count=1,
                payload={},
                occurred_at=now - timedelta(days=10),
            ),
            CloudSaleFact(
                source_event_id=growth_current_event.id,
                organization_id=org.id,
                branch_id=branch_growth.id,
                source_device_id=device_growth.id,
                local_sale_id=2,
                invoice_number="GROW-CUR",
                total_amount=Decimal("80.00"),
                payment_method="cash",
                item_count=1,
                payload={},
                occurred_at=now - timedelta(days=2),
            ),
        ]
    )
    db_session.commit()
    report_user = _report_user(db_session, org.id)

    comparison = get_cloud_revenue_comparison(
        organization_id=org.id,
        period_days=7,
        limit=10,
        db=db_session,
        current_user=report_user,
    )

    assert comparison.current_revenue == 90.0
    assert comparison.previous_revenue == 120.0
    assert comparison.revenue_change == -30.0
    assert comparison.revenue_change_percent == -25.0
    assert comparison.anomaly_count == 1
    assert comparison.branches[0].branch_id == branch_drop.id
    assert comparison.branches[0].status == "severe_drop"
    growth = next(item for item in comparison.branches if item.branch_id == branch_growth.id)
    assert growth.status == "growth"
    assert growth.revenue_change_percent == 300.0


def test_cloud_revenue_comparison_respects_branch_scope(db_session):
    org, branch, device = _tenant(db_session, name="Trend Scoped Org", branch_code="TS")
    event = _ingested(db_session, org, branch, device, event_id="13131313-1313-1313-1313-131313131313", sequence=1, event_type=SyncEventType.SALE_CREATED)
    now = datetime.now(timezone.utc)
    db_session.add(
        CloudSaleFact(
            source_event_id=event.id,
            organization_id=org.id,
            branch_id=branch.id,
            source_device_id=device.id,
            local_sale_id=1,
            invoice_number="TS-1",
            total_amount=Decimal("50.00"),
            payment_method="cash",
            item_count=1,
            payload={},
            occurred_at=now - timedelta(days=1),
        )
    )
    db_session.commit()
    report_user = _report_user(db_session, org.id, branch_id=branch.id, username="trend-branch-user")

    comparison = get_cloud_revenue_comparison(
        organization_id=org.id,
        period_days=7,
        limit=10,
        db=db_session,
        current_user=report_user,
    )

    assert comparison.branch_id == branch.id
    assert comparison.branch_count == 1
    assert comparison.branches[0].branch_id == branch.id
    assert comparison.branches[0].status == "new_sales"


def test_cloud_reconciliation_flags_projection_and_snapshot_inconsistencies(db_session):
    org, branch, device = _tenant(db_session, name="Reconcile Org", branch_code="REC")
    other_org, other_branch, other_device = _tenant(db_session, name="Other Reconcile Org", branch_code="OREC")
    event = _ingested(db_session, org, branch, device, event_id="88888888-8888-8888-8888-888888888881", sequence=1, event_type=SyncEventType.PRODUCT_CREATED)
    movement_event = _ingested(db_session, org, branch, device, event_id="88888888-8888-8888-8888-888888888882", sequence=2, event_type=SyncEventType.STOCK_ADJUSTED)
    failed_event = _ingested(db_session, org, branch, device, event_id="88888888-8888-8888-8888-888888888883", sequence=3, event_type=SyncEventType.STOCK_RECEIVED)
    other_event = _ingested(db_session, other_org, other_branch, other_device, event_id="88888888-8888-8888-8888-888888888884", sequence=1, event_type=SyncEventType.PRODUCT_CREATED)
    failed_event.projection_error = "bad payload"
    db_session.add_all(
        [
            CloudProductSnapshot(
                organization_id=org.id,
                branch_id=branch.id,
                local_product_id=10,
                name="Mismatch Tabs",
                sku="MM-10",
                total_stock=5,
                low_stock_threshold=2,
                is_active=True,
                last_source_event_id=event.id,
                payload={},
            ),
            CloudProductSnapshot(
                organization_id=org.id,
                branch_id=branch.id,
                local_product_id=11,
                name="Negative Syrup",
                sku="NEG-11",
                total_stock=-1,
                low_stock_threshold=2,
                is_active=True,
                last_source_event_id=event.id,
                payload={},
            ),
            CloudProductSnapshot(
                organization_id=other_org.id,
                branch_id=other_branch.id,
                local_product_id=10,
                name="Other Product",
                sku="OTHER",
                total_stock=0,
                low_stock_threshold=2,
                is_active=True,
                last_source_event_id=other_event.id,
                payload={},
            ),
            CloudBatchSnapshot(
                organization_id=org.id,
                branch_id=branch.id,
                local_product_id=10,
                local_batch_id=100,
                batch_number="B-100",
                quantity=3,
                expiry_date=date.today() + timedelta(days=100),
                is_quarantined=False,
                last_source_event_id=event.id,
                payload={},
            ),
            CloudBatchSnapshot(
                organization_id=org.id,
                branch_id=branch.id,
                local_product_id=99,
                local_batch_id=999,
                batch_number="ORPHAN",
                quantity=-2,
                expiry_date=date.today() + timedelta(days=100),
                is_quarantined=False,
                last_source_event_id=event.id,
                payload={},
            ),
            CloudInventoryMovementFact(
                source_event_id=movement_event.id,
                line_number=1,
                organization_id=org.id,
                branch_id=branch.id,
                source_device_id=device.id,
                event_type=SyncEventType.STOCK_ADJUSTED.value,
                local_product_id=10,
                local_batch_id=100,
                quantity_delta=2,
                stock_after=4,
                payload={},
            ),
        ]
    )
    db_session.commit()
    report_user = _report_user(db_session, org.id, branch_id=branch.id, username="reconcile-report-user")

    summary = get_cloud_reconciliation(
        organization_id=org.id,
        limit=50,
        db=db_session,
        current_user=report_user,
    )

    issue_types = {issue.issue_type for issue in summary.issues}
    assert summary.branch_id == branch.id
    assert summary.product_snapshot_count == 2
    assert summary.batch_snapshot_count == 2
    assert summary.projection_failed_count == 1
    assert summary.issue_count >= 5
    assert summary.critical_issue_count >= 2
    assert "product_batch_quantity_mismatch" in issue_types
    assert "latest_movement_stock_after_mismatch" in issue_types
    assert "negative_product_stock" in issue_types
    assert "negative_batch_quantity" in issue_types
    assert "orphan_batch_snapshot" in issue_types
    assert "projection_failures_present" in issue_types
    assert all(issue.issue_key for issue in summary.issues)


def test_manager_can_acknowledge_and_resolve_cloud_reconciliation_issue(db_session):
    org, branch, user = _seed_reconciliation_issue(db_session)
    summary = get_cloud_reconciliation(
        organization_id=org.id,
        limit=50,
        db=db_session,
        current_user=user,
    )
    issue = summary.issues[0]

    acknowledged = acknowledge_cloud_reconciliation_issue(
        CloudReconciliationIssueActionRequest(
            organization_id=org.id,
            branch_id=branch.id,
            issue_key=issue.issue_key,
            notes="Inventory count scheduled before trading.",
        ),
        db=db_session,
        current_user=user,
    )
    acknowledged_summary = get_cloud_reconciliation(
        organization_id=org.id,
        limit=50,
        db=db_session,
        current_user=user,
    )
    acknowledged_issue = next(item for item in acknowledged_summary.issues if item.issue_key == issue.issue_key)

    assert acknowledged.status == "acknowledged"
    assert acknowledged.issue_key == issue.issue_key
    assert acknowledged_issue.acknowledgement_status == "acknowledged"
    assert acknowledged_issue.acknowledged_by_user_id == user.id
    assert acknowledged_issue.acknowledgement_notes == "Inventory count scheduled before trading."

    resolved = resolve_cloud_reconciliation_issue(
        CloudReconciliationIssueActionRequest(
            organization_id=org.id,
            branch_id=branch.id,
            issue_key=issue.issue_key,
            notes="Branch manager confirmed correction plan.",
        ),
        db=db_session,
        current_user=user,
    )
    resolved_summary = get_cloud_reconciliation(
        organization_id=org.id,
        limit=50,
        db=db_session,
        current_user=user,
    )
    resolved_issue = next(item for item in resolved_summary.issues if item.issue_key == issue.issue_key)
    audit_actions = {
        entry.action
        for entry in db_session.query(ActivityLog)
        .filter(ActivityLog.entity_type == "cloud_reconciliation_issue")
        .all()
    }

    assert resolved.status == "resolved"
    assert resolved_issue.acknowledgement_status == "resolved"
    assert resolved_issue.resolved_by_user_id == user.id
    assert resolved_issue.resolution_notes == "Branch manager confirmed correction plan."
    assert "acknowledge_cloud_reconciliation_issue" in audit_actions
    assert "resolve_cloud_reconciliation_issue" in audit_actions


def test_acknowledging_unknown_cloud_reconciliation_issue_returns_404(db_session):
    org, branch, user = _seed_reconciliation_issue(db_session)

    with pytest.raises(HTTPException) as exc:
        acknowledge_cloud_reconciliation_issue(
            CloudReconciliationIssueActionRequest(
                organization_id=org.id,
                branch_id=branch.id,
                issue_key="missing",
            ),
            db=db_session,
            current_user=user,
        )

    assert exc.value.status_code == 404


def test_admin_can_repair_product_stock_total_mismatch(db_session):
    org, branch, device = _tenant(db_session, name="Repair Mismatch Org", branch_code="RMO")
    event = _ingested(
        db_session,
        org,
        branch,
        device,
        event_id="99999999-9999-9999-9999-999999999992",
        sequence=1,
        event_type=SyncEventType.PRODUCT_CREATED,
    )
    db_session.add_all(
        [
            CloudProductSnapshot(
                organization_id=org.id,
                branch_id=branch.id,
                local_product_id=44,
                name="Repair Stock Tabs",
                sku="RST-44",
                total_stock=9,
                low_stock_threshold=2,
                is_active=True,
                last_source_event_id=event.id,
                payload={},
            ),
            CloudBatchSnapshot(
                organization_id=org.id,
                branch_id=branch.id,
                local_product_id=44,
                local_batch_id=440,
                batch_number="RST-440",
                quantity=4,
                expiry_date=date.today() + timedelta(days=100),
                is_quarantined=False,
                last_source_event_id=event.id,
                payload={},
            ),
        ]
    )
    db_session.commit()
    user = _report_user(
        db_session,
        org.id,
        branch_id=branch.id,
        username="repair-mismatch-user",
        role=UserRole.ADMIN,
    )
    summary = get_cloud_reconciliation(
        organization_id=org.id,
        limit=50,
        db=db_session,
        current_user=user,
    )
    issue = next(item for item in summary.issues if item.issue_type == "product_batch_quantity_mismatch")

    result = repair_cloud_reconciliation_issue(
        CloudReconciliationRepairRequest(
            organization_id=org.id,
            branch_id=branch.id,
            issue_key=issue.issue_key,
            repair_type="rebuild_product_stock_total",
            notes="Rebuild cloud read model from batches.",
        ),
        db=db_session,
        current_user=user,
    )
    product = db_session.query(CloudProductSnapshot).filter_by(local_product_id=44).one()
    repaired_summary = get_cloud_reconciliation(
        organization_id=org.id,
        limit=50,
        db=db_session,
        current_user=user,
    )
    audit_entry = (
        db_session.query(ActivityLog)
        .filter(ActivityLog.action == "repair_cloud_reconciliation_issue")
        .order_by(ActivityLog.id.desc())
        .first()
    )

    assert result.repaired == 1
    assert product.total_stock == 4
    assert "product_batch_quantity_mismatch" not in {item.issue_type for item in repaired_summary.issues}
    assert audit_entry is not None
    assert audit_entry.extra_data["repair_type"] == "rebuild_product_stock_total"


def test_admin_can_retry_failed_projection_repair(db_session):
    org, branch, device = _tenant(db_session, name="Repair Projection Org", branch_code="RPO")
    event = _ingested(
        db_session,
        org,
        branch,
        device,
        event_id="99999999-9999-9999-9999-999999999993",
        sequence=1,
        event_type=SyncEventType.PRODUCT_CREATED,
    )
    event.projection_error = "temporary projection failure"
    event.payload = {
        "product_id": 72,
        "name": "Projection Repair Tabs",
        "sku": "PRT-72",
        "total_stock": 6,
        "low_stock_threshold": 2,
        "is_active": True,
    }
    db_session.commit()
    user = _report_user(
        db_session,
        org.id,
        branch_id=branch.id,
        username="repair-projection-user",
        role=UserRole.ADMIN,
    )

    result = repair_cloud_reconciliation_issue(
        CloudReconciliationRepairRequest(
            organization_id=org.id,
            branch_id=branch.id,
            repair_type="retry_failed_projections",
            notes="Retry after projector fix.",
            limit=10,
        ),
        db=db_session,
        current_user=user,
    )
    db_session.refresh(event)
    product = db_session.query(CloudProductSnapshot).filter_by(local_product_id=72).one()

    assert result.attempted == 1
    assert result.repaired == 1
    assert event.projected_at is not None
    assert event.projection_error is None


def test_admin_can_repair_cloud_sale_item_counts_from_sale_payload(db_session):
    org, branch, device = _tenant(db_session, name="Repair Sale Units Org", branch_code="RSU")
    event = _ingested(
        db_session,
        org,
        branch,
        device,
        event_id="99999999-9999-9999-9999-999999999994",
        sequence=1,
        event_type=SyncEventType.SALE_CREATED,
    )
    event.payload = {
        "sale_id": 314,
        "invoice_number": "INV-RSU-314",
        "total_amount": "120.00",
        "payment_method": "cash",
        "items": [
            {"product_id": 10, "quantity": 5, "unit_price": "10.00"},
            {"product_id": 20, "quantity": 6, "unit_price": "11.67"},
        ],
    }
    db_session.add(
        CloudSaleFact(
            source_event_id=event.id,
            organization_id=org.id,
            branch_id=branch.id,
            source_device_id=device.id,
            local_sale_id=314,
            invoice_number="INV-RSU-314",
            total_amount=Decimal("120.00"),
            payment_method="cash",
            item_count=2,
            payload={"old": "line-count semantics"},
        )
    )
    db_session.commit()
    user = _report_user(
        db_session,
        org.id,
        branch_id=branch.id,
        username="repair-sale-units-user",
        role=UserRole.ADMIN,
    )

    result = repair_cloud_reconciliation_issue(
        CloudReconciliationRepairRequest(
            organization_id=org.id,
            branch_id=branch.id,
            repair_type="repair_sale_item_counts",
            notes="Align cloud units sold with local dashboard.",
            limit=10,
        ),
        db=db_session,
        current_user=user,
    )
    fact = db_session.query(CloudSaleFact).filter_by(local_sale_id=314).one()
    audit_entry = (
        db_session.query(ActivityLog)
        .filter(ActivityLog.action == "repair_cloud_reconciliation_issue")
        .order_by(ActivityLog.id.desc())
        .first()
    )

    assert result.attempted == 1
    assert result.repaired == 1
    assert result.skipped == 0
    assert fact.item_count == 11
    assert fact.payload == event.payload
    assert audit_entry is not None
    assert audit_entry.extra_data["repair_type"] == "repair_sale_item_counts"


def test_cloud_dead_stock_identifies_products_with_no_sales(db_session):
    org, branch, device = _tenant(db_session, name="Dead Stock Org", branch_code="DSO")
    user = _report_user(db_session, org.id, username="dead-stock-user")
    sale_event = _ingested(
        db_session, org, branch, device,
        event_id="dd000001-0000-0000-0000-000000000001",
        sequence=1,
        event_type=SyncEventType.SALE_CREATED,
    )
    now = datetime.now(timezone.utc)
    # Product 1: has stock but no sale movements → dead stock.
    # Product 2: has stock and a recent sale movement → should NOT appear.
    db_session.add_all([
        CloudProductSnapshot(
            organization_id=org.id, branch_id=branch.id, local_product_id=101,
            name="Stagnant Drops", sku="STAG-1", total_stock=50, low_stock_threshold=5,
            is_active=True, last_source_event_id=sale_event.id, payload={},
        ),
        CloudProductSnapshot(
            organization_id=org.id, branch_id=branch.id, local_product_id=102,
            name="Active Tabs", sku="ACT-2", total_stock=30, low_stock_threshold=5,
            is_active=True, last_source_event_id=sale_event.id, payload={},
        ),
        CloudInventoryMovementFact(
            source_event_id=sale_event.id, line_number=1,
            organization_id=org.id, branch_id=branch.id, source_device_id=device.id,
            local_product_id=102, quantity_delta=-10,
            event_type=SyncEventType.SALE_CREATED.value, payload={},
            occurred_at=now - timedelta(days=1),
        ),
    ])
    db_session.commit()

    result = get_cloud_dead_stock(
        organization_id=org.id, branch_id=None, period_days=30, limit=50,
        db=db_session, current_user=user,
    )

    product_names = [item.product_name for item in result]
    assert "Stagnant Drops" in product_names, "Product with no sales must be flagged"
    assert "Active Tabs" not in product_names, "Product with recent sales must not be flagged"
    stagnant = next(item for item in result if item.product_name == "Stagnant Drops")
    assert stagnant.status == "dead_stock"
    assert stagnant.units_sold_in_period == 0
    assert stagnant.branch_name == branch.name


def test_cloud_dead_stock_slow_mover_below_threshold(db_session):
    org, branch, device = _tenant(db_session, name="Slow Mover Org", branch_code="SMO")
    user = _report_user(db_session, org.id, username="slow-mover-user")
    sale_event = _ingested(
        db_session, org, branch, device,
        event_id="dd000002-0000-0000-0000-000000000002",
        sequence=1,
        event_type=SyncEventType.SALE_CREATED,
    )
    now = datetime.now(timezone.utc)
    # Product 1: 1 unit sold over 30 days → avg 0.033/day → slow_mover.
    # Product 2: 20 units sold over 30 days → avg 0.67/day → above threshold → excluded.
    db_session.add_all([
        CloudProductSnapshot(
            organization_id=org.id, branch_id=branch.id, local_product_id=201,
            name="Slow Ointment", sku="SLOW-1", total_stock=100, low_stock_threshold=5,
            is_active=True, last_source_event_id=sale_event.id, payload={},
        ),
        CloudProductSnapshot(
            organization_id=org.id, branch_id=branch.id, local_product_id=202,
            name="Fast Capsule", sku="FAST-2", total_stock=50, low_stock_threshold=5,
            is_active=True, last_source_event_id=sale_event.id, payload={},
        ),
        CloudInventoryMovementFact(
            source_event_id=sale_event.id, line_number=1,
            organization_id=org.id, branch_id=branch.id, source_device_id=device.id,
            local_product_id=201, quantity_delta=-1,
            event_type=SyncEventType.SALE_CREATED.value, payload={},
            occurred_at=now - timedelta(days=5),
        ),
        CloudInventoryMovementFact(
            source_event_id=sale_event.id, line_number=2,
            organization_id=org.id, branch_id=branch.id, source_device_id=device.id,
            local_product_id=202, quantity_delta=-20,
            event_type=SyncEventType.SALE_CREATED.value, payload={},
            occurred_at=now - timedelta(days=5),
        ),
    ])
    db_session.commit()

    result = get_cloud_dead_stock(
        organization_id=org.id, branch_id=None, period_days=30, limit=50,
        db=db_session, current_user=user,
    )

    product_names = [item.product_name for item in result]
    assert "Slow Ointment" in product_names, "Slow mover must be flagged"
    assert "Fast Capsule" not in product_names, "Fast mover must not be flagged"
    slow = next(item for item in result if item.product_name == "Slow Ointment")
    assert slow.status == "slow_mover"
    assert slow.units_sold_in_period == 1


def test_cloud_dead_stock_respects_branch_scope(db_session):
    org, branch, device = _tenant(db_session, name="Dead Scope Org", branch_code="DSB")
    other_branch = Branch(organization_id=org.id, name="Other Branch", code="OTH")
    db_session.add(other_branch)
    db_session.flush()
    user = _report_user(db_session, org.id, username="dead-scope-user")
    sale_event = _ingested(
        db_session, org, branch, device,
        event_id="dd000003-0000-0000-0000-000000000003",
        sequence=1,
        event_type=SyncEventType.SALE_CREATED,
    )
    db_session.add_all([
        CloudProductSnapshot(
            organization_id=org.id, branch_id=branch.id, local_product_id=301,
            name="Branch 1 Dead", sku="B1D-1", total_stock=10, low_stock_threshold=2,
            is_active=True, last_source_event_id=sale_event.id, payload={},
        ),
        CloudProductSnapshot(
            organization_id=org.id, branch_id=other_branch.id, local_product_id=302,
            name="Branch 2 Dead", sku="B2D-2", total_stock=10, low_stock_threshold=2,
            is_active=True, last_source_event_id=sale_event.id, payload={},
        ),
    ])
    db_session.commit()

    result = get_cloud_dead_stock(
        organization_id=org.id, branch_id=branch.id, period_days=30, limit=50,
        db=db_session, current_user=user,
    )

    product_names = [item.product_name for item in result]
    assert "Branch 1 Dead" in product_names
    assert "Branch 2 Dead" not in product_names, "Other branch items must be excluded when branch_id is scoped"
