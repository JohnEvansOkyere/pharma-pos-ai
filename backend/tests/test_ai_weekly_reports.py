from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.api.endpoints.ai_manager import (
    generate_weekly_manager_report,
    get_weekly_manager_report,
    list_weekly_manager_reports,
)
from app.core.config import settings
from app.core.security import get_password_hash
from app.models import Branch, Device, Organization
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
from app.schemas.ai_manager import AIWeeklyReportGenerateRequest
from app.services.ai_weekly_report_service import AIWeeklyReportService
from app.services.scheduler import SchedulerService


def _tenant(db_session):
    organization = Organization(name="Weekly Report Tenant")
    db_session.add(organization)
    db_session.flush()
    branch_a = Branch(organization_id=organization.id, name="Main Branch", code="MAIN")
    branch_b = Branch(organization_id=organization.id, name="Second Branch", code="SECOND")
    db_session.add_all([branch_a, branch_b])
    db_session.flush()
    device_a = Device(
        organization_id=organization.id,
        branch_id=branch_a.id,
        device_uid="weekly-device-a",
        name="Weekly Device A",
        status=DeviceStatus.ACTIVE,
    )
    device_b = Device(
        organization_id=organization.id,
        branch_id=branch_b.id,
        device_uid="weekly-device-b",
        name="Weekly Device B",
        status=DeviceStatus.ACTIVE,
    )
    db_session.add_all([device_a, device_b])
    db_session.commit()
    return organization, branch_a, branch_b, device_a, device_b


def _manager(db_session, organization_id: int, *, branch_id=None, username="weekly-manager"):
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("manager-secret"),
        full_name="Weekly Manager",
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
        aggregate_type="sale" if event_type == SyncEventType.SALE_CREATED else "stock",
        aggregate_id=sequence,
        schema_version=1,
        payload={"id": sequence},
        payload_hash=str(sequence) * 64,
        duplicate_count=0,
        received_at=datetime(2026, 5, 2, 14, 0, tzinfo=timezone.utc),
        projected_at=datetime(2026, 5, 2, 14, 1, tzinfo=timezone.utc),
    )
    db_session.add(event)
    db_session.commit()
    return event


def _seed_report_data(db_session, organization, branch_a, branch_b, device_a, device_b):
    sale_event_a = _ingested(
        db_session,
        organization,
        branch_a,
        device_a,
        event_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        sequence=1,
        event_type=SyncEventType.SALE_CREATED,
    )
    sale_event_b = _ingested(
        db_session,
        organization,
        branch_b,
        device_b,
        event_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        sequence=1,
        event_type=SyncEventType.SALE_CREATED,
    )
    stock_event = _ingested(
        db_session,
        organization,
        branch_a,
        device_a,
        event_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        sequence=2,
        event_type=SyncEventType.STOCK_ADJUSTED,
    )
    product_event = _ingested(
        db_session,
        organization,
        branch_a,
        device_a,
        event_id="dddddddd-dddd-dddd-dddd-dddddddddddd",
        sequence=3,
        event_type=SyncEventType.PRODUCT_CREATED,
    )
    sale_created_at = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    db_session.add_all(
        [
            CloudSaleFact(
                source_event_id=sale_event_a.id,
                organization_id=organization.id,
                branch_id=branch_a.id,
                source_device_id=device_a.id,
                local_sale_id=1,
                invoice_number="A-100",
                total_amount=Decimal("120.00"),
                payment_method="cash",
                item_count=4,
                payload={},
                created_at=sale_created_at,
            ),
            CloudSaleFact(
                source_event_id=sale_event_b.id,
                organization_id=organization.id,
                branch_id=branch_b.id,
                source_device_id=device_b.id,
                local_sale_id=2,
                invoice_number="B-100",
                total_amount=Decimal("250.00"),
                payment_method="cash",
                item_count=8,
                payload={},
                created_at=sale_created_at,
            ),
            CloudInventoryMovementFact(
                source_event_id=stock_event.id,
                line_number=1,
                organization_id=organization.id,
                branch_id=branch_a.id,
                source_device_id=device_a.id,
                event_type=SyncEventType.STOCK_ADJUSTED.value,
                local_product_id=10,
                local_batch_id=20,
                quantity_delta=-3,
                stock_after=0,
                payload={},
                created_at=sale_created_at,
            ),
            CloudProductSnapshot(
                organization_id=organization.id,
                branch_id=branch_a.id,
                local_product_id=10,
                name="Critical Antibiotic",
                sku="CRIT-AB",
                total_stock=0,
                low_stock_threshold=5,
                reorder_level=12,
                is_active=True,
                last_source_event_id=product_event.id,
                payload={},
            ),
            CloudBatchSnapshot(
                organization_id=organization.id,
                branch_id=branch_a.id,
                local_product_id=10,
                local_batch_id=20,
                batch_number="EXP-WEEK",
                quantity=6,
                expiry_date=date(2026, 5, 6),
                cost_price=Decimal("3.50"),
                is_quarantined=False,
                last_source_event_id=product_event.id,
                payload={},
            ),
        ]
    )
    db_session.commit()


def test_weekly_report_service_generates_saved_performance_and_action_report(monkeypatch, db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_report_data(db_session, organization, branch_a, branch_b, device_a, device_b)
    monkeypatch.setattr(settings, "AI_MANAGER_PROVIDER", "deterministic")
    monkeypatch.setattr(settings, "AI_MANAGER_MODEL", None)

    report = AIWeeklyReportService.generate_for_organization(
        db_session,
        organization_id=organization.id,
        as_of=datetime(2026, 5, 3, 19, 0, tzinfo=timezone.utc),
    )

    assert report.id is not None
    assert report.action_period_start == date(2026, 5, 4)
    assert report.action_period_end == date(2026, 5, 10)
    assert report.sections["performance_review"]["total_revenue"] == 370.0
    assert report.sections["coming_week_action_plan"]["risk_counts"]["out_of_stock_count"] == 1
    assert report.sections["coming_week_action_plan"]["risk_counts"]["near_expiry_batch_count"] == 1
    assert report.sections["sync_and_data_quality"]["projection_failed_count"] == 0
    assert report.provider == "deterministic"
    assert report.fallback_used is False
    assert "controlled-drug" in " ".join(report.safety_notes)


def test_weekly_report_endpoint_persists_report_and_lists_it(monkeypatch, db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_report_data(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id)
    monkeypatch.setattr(settings, "AI_MANAGER_PROVIDER", "deterministic")

    generated = generate_weekly_manager_report(
        AIWeeklyReportGenerateRequest(organization_id=organization.id, branch_id=branch_a.id),
        db=db_session,
        current_user=manager,
    )
    reports = list_weekly_manager_reports(
        organization_id=organization.id,
        branch_id=branch_a.id,
        limit=20,
        db=db_session,
        current_user=manager,
    )
    fetched = get_weekly_manager_report(generated.id, db=db_session, current_user=manager)

    assert generated.branch_id == branch_a.id
    assert reports[0].id == generated.id
    assert fetched.tool_results["stock_risks"]["out_of_stock_count"] == 1
    assert fetched.sections["coming_week_action_plan"]["risk_counts"]["out_of_stock_count"] == 1


def test_branch_manager_cannot_generate_cross_branch_report(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_report_data(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id, branch_id=branch_a.id, username="branch-weekly-manager")

    with pytest.raises(HTTPException) as exc:
        generate_weekly_manager_report(
            AIWeeklyReportGenerateRequest(organization_id=organization.id, branch_id=branch_b.id),
            db=db_session,
            current_user=manager,
        )

    assert exc.value.status_code == 403
    assert "Branch access denied" in exc.value.detail


def test_weekly_report_scheduler_job_is_registered_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_BACKGROUND_SCHEDULER", True)
    monkeypatch.setattr(settings, "AI_WEEKLY_REPORTS_ENABLED", True)
    monkeypatch.setattr(settings, "AI_WEEKLY_REPORT_DAY", "sun")
    monkeypatch.setattr(settings, "AI_WEEKLY_REPORT_HOUR", 19)
    monkeypatch.setattr(settings, "AI_WEEKLY_REPORT_MINUTE", 0)

    scheduler_service = SchedulerService()
    scheduler_service.start()
    try:
        job = scheduler_service.scheduler.get_job("generate_weekly_ai_reports")
        assert job is not None
        assert job.name == "Generate weekly AI manager reports"
    finally:
        scheduler_service.stop()
