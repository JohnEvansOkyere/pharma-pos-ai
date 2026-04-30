from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.api.endpoints.ai_manager import (
    deliver_weekly_manager_report,
    generate_weekly_manager_report,
    get_weekly_report_delivery_setting,
    get_weekly_manager_report,
    list_weekly_report_deliveries,
    list_weekly_manager_reports,
    review_weekly_manager_report,
    upsert_weekly_report_delivery_setting,
)
from app.core.config import settings
from app.core.security import get_password_hash
from app.models import Branch, Device, Organization
from app.models.ai_report import AIWeeklyReportDeliverySetting
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
from app.schemas.ai_manager import (
    AIWeeklyReportDeliverRequest,
    AIWeeklyReportDeliverySettingUpsert,
    AIWeeklyReportGenerateRequest,
    AIWeeklyReportReviewRequest,
)
from app.services.ai_report_delivery_service import AIReportDeliveryService
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


def _admin(db_session, organization_id: int, *, username="weekly-admin"):
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("admin-secret"),
        full_name="Weekly Admin",
        role=UserRole.ADMIN,
        organization_id=organization_id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _delivery_setting(
    db_session,
    organization_id: int,
    *,
    branch_id=None,
    email_recipients=None,
    telegram_chat_ids=None,
):
    setting = AIWeeklyReportDeliverySetting(
        organization_id=organization_id,
        branch_id=branch_id,
        report_scope_key=AIWeeklyReportService.scope_key(branch_id),
        email_enabled=True,
        email_recipients=email_recipients or ["owner@example.com"],
        telegram_enabled=True,
        telegram_chat_ids=telegram_chat_ids or ["12345"],
        is_active=True,
    )
    db_session.add(setting)
    db_session.commit()
    return setting


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
    assert report.sections["sync_and_data_quality"]["reconciliation"]["issue_count"] >= 1
    assert report.provider == "deterministic"
    assert report.fallback_used is False
    assert "controlled-drug" in " ".join(report.safety_notes)


def test_weekly_report_generation_is_idempotent_for_same_scope_and_action_period(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_report_data(db_session, organization, branch_a, branch_b, device_a, device_b)
    as_of = datetime(2026, 5, 3, 19, 0, tzinfo=timezone.utc)

    first = AIWeeklyReportService.generate_for_organization(
        db_session,
        organization_id=organization.id,
        branch_id=branch_a.id,
        as_of=as_of,
    )
    second = AIWeeklyReportService.generate_for_organization(
        db_session,
        organization_id=organization.id,
        branch_id=branch_a.id,
        as_of=as_of,
    )
    forced = AIWeeklyReportService.generate_for_organization(
        db_session,
        organization_id=organization.id,
        branch_id=branch_a.id,
        as_of=as_of,
        idempotent=False,
    )

    assert second.id == first.id
    assert forced.id == first.id


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


def test_manager_can_mark_weekly_report_reviewed(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_report_data(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id)
    report = AIWeeklyReportService.generate_for_organization(
        db_session,
        organization_id=organization.id,
        branch_id=branch_a.id,
        as_of=datetime(2026, 5, 3, 19, 0, tzinfo=timezone.utc),
    )

    reviewed = review_weekly_manager_report(
        report.id,
        AIWeeklyReportReviewRequest(review_notes="  Check branch expiry shelf today.  "),
        db=db_session,
        current_user=manager,
    )
    fetched = get_weekly_manager_report(report.id, db=db_session, current_user=manager)

    assert reviewed.reviewed_by_user_id == manager.id
    assert reviewed.reviewed_at is not None
    assert reviewed.review_notes == "Check branch expiry shelf today."
    assert fetched.reviewed_by_user_id == manager.id
    assert fetched.review_notes == "Check branch expiry shelf today."


def test_weekly_report_delivery_records_email_and_telegram_attempts(monkeypatch, db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_report_data(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id)
    report = AIWeeklyReportService.generate_for_organization(
        db_session,
        organization_id=organization.id,
        branch_id=branch_a.id,
        as_of=datetime(2026, 5, 3, 19, 0, tzinfo=timezone.utc),
    )
    _delivery_setting(db_session, organization.id, branch_id=branch_a.id)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "reports@example.com")
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "telegram-token")
    monkeypatch.setattr(AIReportDeliveryService, "_send_email", lambda **kwargs: None)
    monkeypatch.setattr(AIReportDeliveryService, "_send_telegram", lambda **kwargs: {"ok": True})

    deliveries = deliver_weekly_manager_report(
        report.id,
        AIWeeklyReportDeliverRequest(),
        db=db_session,
        current_user=manager,
    )

    assert {delivery.channel for delivery in deliveries} == {"email", "telegram"}
    assert all(delivery.status == "sent" for delivery in deliveries)
    assert {delivery.recipient for delivery in deliveries} == {"owner@example.com", "12345"}


def test_transient_failed_weekly_report_delivery_is_retried(monkeypatch, db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_report_data(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id)
    report = AIWeeklyReportService.generate_for_organization(
        db_session,
        organization_id=organization.id,
        branch_id=branch_a.id,
        as_of=datetime(2026, 5, 3, 19, 0, tzinfo=timezone.utc),
    )
    _delivery_setting(db_session, organization.id, branch_id=branch_a.id)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "reports@example.com")
    monkeypatch.setattr(settings, "AI_WEEKLY_REPORT_DELIVERY_MAX_ATTEMPTS", 3)
    attempts = {"count": 0}

    def flaky_email(**kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise TimeoutError("temporary smtp timeout")

    monkeypatch.setattr(AIReportDeliveryService, "_send_email", flaky_email)

    deliveries = deliver_weekly_manager_report(
        report.id,
        AIWeeklyReportDeliverRequest(channels=["email"]),
        db=db_session,
        current_user=manager,
    )
    failed = deliveries[0]
    failed.next_retry_at = datetime(2026, 5, 3, 19, 1, tzinfo=timezone.utc)
    db_session.commit()

    retried = AIReportDeliveryService.retry_due(
        db_session,
        now=datetime(2026, 5, 3, 19, 2, tzinfo=timezone.utc),
    )

    assert len(retried) == 1
    assert retried[0].status == "sent"
    assert retried[0].attempt_count == 2
    assert retried[0].retryable is False
    assert retried[0].next_retry_at is None


def test_permanent_delivery_configuration_failure_is_not_retried(monkeypatch, db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_report_data(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id)
    report = AIWeeklyReportService.generate_for_organization(
        db_session,
        organization_id=organization.id,
        branch_id=branch_a.id,
        as_of=datetime(2026, 5, 3, 19, 0, tzinfo=timezone.utc),
    )
    _delivery_setting(db_session, organization.id, branch_id=branch_a.id)
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", None)

    deliveries = deliver_weekly_manager_report(
        report.id,
        AIWeeklyReportDeliverRequest(channels=["email"]),
        db=db_session,
        current_user=manager,
    )
    failed = deliveries[0]
    retried = AIReportDeliveryService.retry_due(
        db_session,
        now=datetime(2026, 5, 3, 19, 2, tzinfo=timezone.utc),
    )

    assert failed.status == "failed"
    assert failed.retryable is False
    assert failed.next_retry_at is None
    assert retried == []


def test_retry_stops_at_max_attempts(monkeypatch, db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_report_data(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id)
    report = AIWeeklyReportService.generate_for_organization(
        db_session,
        organization_id=organization.id,
        branch_id=branch_a.id,
        as_of=datetime(2026, 5, 3, 19, 0, tzinfo=timezone.utc),
    )
    _delivery_setting(db_session, organization.id, branch_id=branch_a.id)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "reports@example.com")
    monkeypatch.setattr(settings, "AI_WEEKLY_REPORT_DELIVERY_MAX_ATTEMPTS", 2)

    def always_fail_email(**kwargs):
        raise TimeoutError("still down")

    monkeypatch.setattr(AIReportDeliveryService, "_send_email", always_fail_email)

    deliveries = deliver_weekly_manager_report(
        report.id,
        AIWeeklyReportDeliverRequest(channels=["email"]),
        db=db_session,
        current_user=manager,
    )
    failed = deliveries[0]
    failed.next_retry_at = datetime(2026, 5, 3, 19, 1, tzinfo=timezone.utc)
    db_session.commit()

    retried = AIReportDeliveryService.retry_due(
        db_session,
        now=datetime(2026, 5, 3, 19, 2, tzinfo=timezone.utc),
    )

    assert len(retried) == 1
    assert retried[0].status == "failed"
    assert retried[0].attempt_count == 2
    assert retried[0].retryable is False
    assert retried[0].next_retry_at is None


def test_weekly_report_delivery_history_lists_persisted_attempts(monkeypatch, db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_report_data(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id)
    report = AIWeeklyReportService.generate_for_organization(
        db_session,
        organization_id=organization.id,
        branch_id=branch_a.id,
        as_of=datetime(2026, 5, 3, 19, 0, tzinfo=timezone.utc),
    )
    _delivery_setting(db_session, organization.id, branch_id=branch_a.id)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "reports@example.com")
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "telegram-token")
    monkeypatch.setattr(AIReportDeliveryService, "_send_email", lambda **kwargs: None)
    monkeypatch.setattr(AIReportDeliveryService, "_send_telegram", lambda **kwargs: {"ok": True})

    deliver_weekly_manager_report(
        report.id,
        AIWeeklyReportDeliverRequest(),
        db=db_session,
        current_user=manager,
    )

    history = list_weekly_report_deliveries(
        report.id,
        limit=20,
        db=db_session,
        current_user=manager,
    )

    assert len(history) == 2
    assert {delivery.channel for delivery in history} == {"email", "telegram"}
    assert all(delivery.report_id == report.id for delivery in history)


def test_admin_can_manage_tenant_scoped_delivery_settings(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    admin = _admin(db_session, organization.id)

    saved = upsert_weekly_report_delivery_setting(
        AIWeeklyReportDeliverySettingUpsert(
            organization_id=organization.id,
            branch_id=branch_a.id,
            email_enabled=True,
            email_recipients=[" owner@example.com ", ""],
            telegram_enabled=True,
            telegram_chat_ids=[" 12345 "],
        ),
        db=db_session,
        current_user=admin,
    )
    fetched = get_weekly_report_delivery_setting(
        organization_id=organization.id,
        branch_id=branch_a.id,
        db=db_session,
        current_user=admin,
    )

    assert saved.report_scope_key == f"branch:{branch_a.id}"
    assert fetched.email_recipients == ["owner@example.com"]
    assert fetched.telegram_chat_ids == ["12345"]


def test_weekly_report_delivery_does_not_use_global_recipients_without_tenant_setting(monkeypatch, db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_report_data(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id)
    report = AIWeeklyReportService.generate_for_organization(
        db_session,
        organization_id=organization.id,
        branch_id=branch_a.id,
        as_of=datetime(2026, 5, 3, 19, 0, tzinfo=timezone.utc),
    )
    deliveries = deliver_weekly_manager_report(
        report.id,
        AIWeeklyReportDeliverRequest(),
        db=db_session,
        current_user=manager,
    )

    assert {delivery.channel for delivery in deliveries} == {"email", "telegram"}
    assert all(delivery.status == "skipped" for delivery in deliveries)
    assert all("No active tenant delivery setting" in delivery.error_message for delivery in deliveries)


def test_weekly_report_delivery_is_audited_when_channels_are_disabled(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_report_data(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id)
    report = AIWeeklyReportService.generate_for_organization(
        db_session,
        organization_id=organization.id,
        as_of=datetime(2026, 5, 3, 19, 0, tzinfo=timezone.utc),
    )

    deliveries = deliver_weekly_manager_report(
        report.id,
        AIWeeklyReportDeliverRequest(channels=["email", "telegram"]),
        db=db_session,
        current_user=manager,
    )

    assert {delivery.channel for delivery in deliveries} == {"email", "telegram"}
    assert all(delivery.status == "skipped" for delivery in deliveries)
    assert all(delivery.error_message for delivery in deliveries)


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


def test_branch_manager_cannot_view_cross_branch_delivery_history(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_report_data(db_session, organization, branch_a, branch_b, device_a, device_b)
    branch_manager = _manager(
        db_session,
        organization.id,
        branch_id=branch_a.id,
        username="branch-delivery-history-manager",
    )
    report = AIWeeklyReportService.generate_for_organization(
        db_session,
        organization_id=organization.id,
        branch_id=branch_b.id,
        as_of=datetime(2026, 5, 3, 19, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(HTTPException) as exc:
        list_weekly_report_deliveries(
            report.id,
            limit=20,
            db=db_session,
            current_user=branch_manager,
        )

    assert exc.value.status_code == 403
    assert "Branch access denied" in exc.value.detail


def test_branch_manager_cannot_review_cross_branch_report(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_report_data(db_session, organization, branch_a, branch_b, device_a, device_b)
    branch_manager = _manager(
        db_session,
        organization.id,
        branch_id=branch_a.id,
        username="branch-review-manager",
    )
    report = AIWeeklyReportService.generate_for_organization(
        db_session,
        organization_id=organization.id,
        branch_id=branch_b.id,
        as_of=datetime(2026, 5, 3, 19, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(HTTPException) as exc:
        review_weekly_manager_report(
            report.id,
            AIWeeklyReportReviewRequest(review_notes="Cross branch review"),
            db=db_session,
            current_user=branch_manager,
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


def test_weekly_report_delivery_retry_scheduler_job_is_registered(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_BACKGROUND_SCHEDULER", True)
    monkeypatch.setattr(settings, "AI_WEEKLY_REPORT_DELIVERY_RETRY_ENABLED", True)
    monkeypatch.setattr(settings, "AI_WEEKLY_REPORT_DELIVERY_RETRY_INTERVAL_MINUTES", 5)

    scheduler_service = SchedulerService()
    scheduler_service.start()
    try:
        job = scheduler_service.scheduler.get_job("retry_weekly_ai_report_deliveries")
        assert job is not None
        assert job.name == "Retry failed weekly AI report deliveries"
    finally:
        scheduler_service.stop()
