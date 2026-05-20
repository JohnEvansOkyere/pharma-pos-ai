from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.api.endpoints.ai_manager import (
    chat_with_ai_manager,
    get_ai_manager_briefing,
    get_external_provider_settings,
    list_ai_findings,
    update_ai_finding_status,
    upsert_external_provider_settings,
)
from app.core.config import settings
from app.core.security import get_password_hash
from app.models import Branch, Device, Organization
from app.models.activity_log import ActivityLog
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
from app.schemas.ai_manager import AIExternalProviderSettingUpsert, AIFindingStatusUpdate, AIManagerChatRequest
from app.services.ai_llm_provider import AIManagerLLMProvider
from app.services.telegram_alert_service import TelegramAlertService


def _tenant(db_session):
    organization = Organization(name="AI Tenant")
    db_session.add(organization)
    db_session.flush()
    branch_a = Branch(organization_id=organization.id, name="Branch A", code="A")
    branch_b = Branch(organization_id=organization.id, name="Branch B", code="B")
    db_session.add_all([branch_a, branch_b])
    db_session.flush()
    device_a = Device(
        organization_id=organization.id,
        branch_id=branch_a.id,
        device_uid="ai-device-a",
        name="AI Device A",
        status=DeviceStatus.ACTIVE,
    )
    device_b = Device(
        organization_id=organization.id,
        branch_id=branch_b.id,
        device_uid="ai-device-b",
        name="AI Device B",
        status=DeviceStatus.ACTIVE,
    )
    db_session.add_all([device_a, device_b])
    db_session.commit()
    return organization, branch_a, branch_b, device_a, device_b


def _manager(db_session, organization_id: int, *, branch_id=None, username="ai-manager"):
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("manager-secret"),
        full_name="AI Manager",
        role=UserRole.MANAGER,
        permissions=[UserPermission.VIEW_REPORTS.value],
        organization_id=organization_id,
        branch_id=branch_id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _admin(db_session, organization_id: int, *, username="ai-admin"):
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("admin-secret"),
        full_name="AI Admin",
        role=UserRole.ADMIN,
        organization_id=organization_id,
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
        payload_hash=str(sequence).zfill(64),
        duplicate_count=0,
    )
    db_session.add(event)
    db_session.commit()
    return event


def _seed_facts(db_session, organization, branch_a, branch_b, device_a, device_b):
    event_a = _ingested(
        db_session,
        organization,
        branch_a,
        device_a,
        event_id="11111111-1111-1111-1111-111111111111",
        sequence=1,
        event_type=SyncEventType.SALE_CREATED,
    )
    event_b = _ingested(
        db_session,
        organization,
        branch_b,
        device_b,
        event_id="22222222-2222-2222-2222-222222222222",
        sequence=1,
        event_type=SyncEventType.SALE_CREATED,
    )
    stock_event = _ingested(
        db_session,
        organization,
        branch_a,
        device_a,
        event_id="33333333-3333-3333-3333-333333333333",
        sequence=2,
        event_type=SyncEventType.STOCK_ADJUSTED,
    )
    event_b.projection_error = "bad payload"
    db_session.add_all(
        [
            CloudSaleFact(
                source_event_id=event_a.id,
                organization_id=organization.id,
                branch_id=branch_a.id,
                source_device_id=device_a.id,
                local_sale_id=1,
                invoice_number="A-1",
                total_amount=Decimal("100.00"),
                payment_method="cash",
                item_count=4,
                payload={},
            ),
            CloudSaleFact(
                source_event_id=event_b.id,
                organization_id=organization.id,
                branch_id=branch_b.id,
                source_device_id=device_b.id,
                local_sale_id=1,
                invoice_number="B-1",
                total_amount=Decimal("300.00"),
                payment_method="cash",
                item_count=9,
                payload={},
            ),
            CloudInventoryMovementFact(
                source_event_id=stock_event.id,
                line_number=1,
                organization_id=organization.id,
                branch_id=branch_a.id,
                source_device_id=device_a.id,
                event_type=SyncEventType.STOCK_ADJUSTED.value,
                local_product_id=1,
                local_batch_id=1,
                quantity_delta=15,
                stock_after=20,
                payload={},
            ),
        ]
    )
    db_session.commit()


def test_ai_manager_answers_from_cloud_reporting_data(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_facts(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id)

    response = chat_with_ai_manager(
        AIManagerChatRequest(
            message="Which branch is performing best?",
            organization_id=organization.id,
            period_days=30,
        ),
        db=db_session,
        current_user=manager,
    )

    assert response.refused is False
    answer_lower = response.answer.lower()
    assert (
        f"branch {branch_b.id}" in answer_lower or branch_b.name.lower() in answer_lower
    ), "Answer must reference the top branch by id or name"
    assert response.data_scope.organization_id == organization.id
    assert response.data_scope.branch_id is None
    assert response.tool_results["sales_summary"]["total_revenue"] == 400.0
    assert response.tool_results["sync_health"]["projection_failed_count"] == 1


def test_ai_manager_today_sales_question_uses_today_window(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    today_event = _ingested(
        db_session,
        organization,
        branch_a,
        device_a,
        event_id="10101010-1010-1010-1010-101010101010",
        sequence=10,
        event_type=SyncEventType.SALE_CREATED,
    )
    old_event = _ingested(
        db_session,
        organization,
        branch_a,
        device_a,
        event_id="20202020-2020-2020-2020-202020202020",
        sequence=11,
        event_type=SyncEventType.SALE_CREATED,
    )
    db_session.add_all(
        [
            CloudSaleFact(
                source_event_id=today_event.id,
                organization_id=organization.id,
                branch_id=branch_a.id,
                source_device_id=device_a.id,
                local_sale_id=10,
                invoice_number="TODAY-1",
                total_amount=Decimal("50.00"),
                payment_method="cash",
                item_count=3,
                payload={},
                occurred_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            ),
            CloudSaleFact(
                source_event_id=old_event.id,
                organization_id=organization.id,
                branch_id=branch_a.id,
                source_device_id=device_a.id,
                local_sale_id=11,
                invoice_number="OLD-1",
                total_amount=Decimal("300.00"),
                payment_method="cash",
                item_count=9,
                payload={},
                occurred_at=datetime.now(timezone.utc) - timedelta(days=2),
            ),
        ]
    )
    db_session.commit()
    manager = _manager(db_session, organization.id)

    response = chat_with_ai_manager(
        AIManagerChatRequest(
            message="what is the total sale for today?",
            organization_id=organization.id,
            period_days=30,
        ),
        db=db_session,
        current_user=manager,
    )

    assert response.data_scope.period_days == 1
    assert response.tool_results["time_window"]["label"] == "today"
    assert response.tool_results["sales_summary"]["total_revenue"] == 50.0
    assert response.tool_results["sales_summary"]["sales_count"] == 1
    assert "today" in response.answer.lower()
    assert "50.00" in response.answer
    assert "30 day" not in response.answer.lower()


def test_ai_manager_today_products_sold_uses_sale_movements_not_stock_risk(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    sale_event = _ingested(
        db_session,
        organization,
        branch_a,
        device_a,
        event_id="30303030-3030-3030-3030-303030303030",
        sequence=12,
        event_type=SyncEventType.SALE_CREATED,
    )
    product_event = _ingested(
        db_session,
        organization,
        branch_a,
        device_a,
        event_id="40404040-4040-4040-4040-404040404040",
        sequence=13,
        event_type=SyncEventType.PRODUCT_CREATED,
    )
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            CloudProductSnapshot(
                organization_id=organization.id,
                branch_id=branch_a.id,
                local_product_id=31,
                name="Menthox",
                sku="MENTH",
                total_stock=38,
                low_stock_threshold=5,
                is_active=True,
                last_source_event_id=product_event.id,
                payload={},
            ),
            CloudProductSnapshot(
                organization_id=organization.id,
                branch_id=branch_a.id,
                local_product_id=32,
                name="Amoxicillin",
                sku="AMOX",
                total_stock=0,
                low_stock_threshold=5,
                is_active=True,
                last_source_event_id=product_event.id,
                payload={},
            ),
            CloudInventoryMovementFact(
                source_event_id=sale_event.id,
                line_number=1,
                organization_id=organization.id,
                branch_id=branch_a.id,
                source_device_id=device_a.id,
                event_type=SyncEventType.SALE_CREATED.value,
                local_product_id=31,
                local_batch_id=31,
                quantity_delta=-2,
                stock_after=None,
                payload={},
                occurred_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            ),
            CloudInventoryMovementFact(
                source_event_id=sale_event.id,
                line_number=2,
                organization_id=organization.id,
                branch_id=branch_a.id,
                source_device_id=device_a.id,
                event_type=SyncEventType.SALE_CREATED.value,
                local_product_id=32,
                local_batch_id=32,
                quantity_delta=-1,
                stock_after=None,
                payload={},
                occurred_at=now - timedelta(days=2),
            ),
        ]
    )
    db_session.commit()
    manager = _manager(db_session, organization.id)

    response = chat_with_ai_manager(
        AIManagerChatRequest(
            message="what drugs did we sell today?",
            organization_id=organization.id,
            period_days=30,
        ),
        db=db_session,
        current_user=manager,
    )

    assert response.data_scope.period_days == 1
    assert response.tool_results["time_window"]["label"] == "today"
    assert response.tool_results["product_sales"] == [
        {
            "branch_id": branch_a.id,
            "product_id": 31,
            "product_name": "Menthox",
            "sku": "MENTH",
            "units_sold": 2,
        }
    ]
    assert "menthox" in response.answer.lower()
    assert "amoxicillin" not in response.answer.lower()
    assert "out of stock" not in response.answer.lower()


def test_ai_manager_limits_branch_assigned_user_to_their_branch(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_facts(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id, branch_id=branch_a.id, username="branch-ai-manager")

    response = chat_with_ai_manager(
        AIManagerChatRequest(
            message="Summarize sales",
            organization_id=organization.id,
            period_days=30,
        ),
        db=db_session,
        current_user=manager,
    )

    assert response.data_scope.branch_id == branch_a.id
    assert response.tool_results["sales_summary"]["total_revenue"] == 100.0
    assert len(response.tool_results["branch_sales"]) == 1
    assert response.tool_results["branch_sales"][0]["branch_id"] == branch_a.id


def test_ai_manager_rejects_cross_branch_request(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_facts(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id, branch_id=branch_a.id, username="limited-ai-manager")

    with pytest.raises(HTTPException) as exc:
        chat_with_ai_manager(
            AIManagerChatRequest(
                message="Summarize sales",
                organization_id=organization.id,
                branch_id=branch_b.id,
            ),
            db=db_session,
            current_user=manager,
        )

    assert exc.value.status_code == 403
    assert "Branch access denied" in exc.value.detail


def test_ai_manager_refuses_clinical_or_mutating_requests(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_facts(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id)

    response = chat_with_ai_manager(
        AIManagerChatRequest(
            message="Can I dispense this controlled drug without prescription and adjust stock?",
            organization_id=organization.id,
        ),
        db=db_session,
        current_user=manager,
    )

    assert response.refused is True
    assert response.tool_results == {}
    assert "cannot provide clinical advice" in response.answer.lower()


def test_ai_manager_answers_stock_risk_questions_from_cloud_snapshots(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_facts(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id)
    event = _ingested(
        db_session,
        organization,
        branch_a,
        device_a,
        event_id="44444444-4444-4444-4444-444444444444",
        sequence=3,
        event_type=SyncEventType.PRODUCT_CREATED,
    )
    sale_event = _ingested(
        db_session,
        organization,
        branch_a,
        device_a,
        event_id="55555555-5555-5555-5555-555555555555",
        sequence=4,
        event_type=SyncEventType.SALE_CREATED,
    )
    db_session.add_all(
        [
            CloudProductSnapshot(
                organization_id=organization.id,
                branch_id=branch_a.id,
                local_product_id=50,
                name="Out Stock",
                sku="OUT",
                total_stock=0,
                low_stock_threshold=5,
                is_active=True,
                last_source_event_id=event.id,
                payload={},
            ),
            CloudBatchSnapshot(
                organization_id=organization.id,
                branch_id=branch_a.id,
                local_product_id=50,
                local_batch_id=60,
                batch_number="EXP",
                quantity=4,
                expiry_date=date.today() + timedelta(days=10),
                cost_price=Decimal("2.00"),
                is_quarantined=False,
                last_source_event_id=event.id,
                payload={},
            ),
            CloudInventoryMovementFact(
                source_event_id=sale_event.id,
                line_number=1,
                organization_id=organization.id,
                branch_id=branch_a.id,
                source_device_id=device_a.id,
                event_type=SyncEventType.SALE_CREATED.value,
                local_product_id=50,
                local_batch_id=60,
                quantity_delta=-6,
                stock_after=None,
                payload={},
                occurred_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            ),
        ]
    )
    db_session.commit()

    response = chat_with_ai_manager(
        AIManagerChatRequest(
            message="What stock risks should I investigate today?",
            organization_id=organization.id,
        ),
        db=db_session,
        current_user=manager,
    )

    assert response.refused is False
    assert "out-of-stock" in response.answer.lower()
    assert response.tool_results["stock_risk"]["out_of_stock_count"] == 1
    assert response.tool_results["stock_risk"]["near_expiry_batch_count"] == 1
    assert response.tool_results["stock_velocity"][0]["product_id"] == 50
    assert response.tool_results["stock_velocity"][0]["units_sold"] == 6


def test_ai_manager_answers_velocity_questions_from_sale_movements(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_facts(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id)
    event = _ingested(
        db_session,
        organization,
        branch_a,
        device_a,
        event_id="66666666-6666-6666-6666-666666666666",
        sequence=5,
        event_type=SyncEventType.SALE_CREATED,
    )
    db_session.add_all(
        [
            CloudProductSnapshot(
                organization_id=organization.id,
                branch_id=branch_a.id,
                local_product_id=70,
                name="Velocity Tabs",
                sku="VEL",
                total_stock=4,
                low_stock_threshold=10,
                is_active=True,
                last_source_event_id=event.id,
                payload={},
            ),
            CloudInventoryMovementFact(
                source_event_id=event.id,
                line_number=1,
                organization_id=organization.id,
                branch_id=branch_a.id,
                source_device_id=device_a.id,
                event_type=SyncEventType.SALE_CREATED.value,
                local_product_id=70,
                local_batch_id=70,
                quantity_delta=-8,
                stock_after=None,
                payload={},
                occurred_at=datetime.now(timezone.utc) - timedelta(days=1),
            ),
        ]
    )
    db_session.commit()

    response = chat_with_ai_manager(
        AIManagerChatRequest(
            message="Which products should I reorder based on days of stock remaining?",
            organization_id=organization.id,
            period_days=4,
        ),
        db=db_session,
        current_user=manager,
    )

    assert response.refused is False
    assert "velocity tabs" in response.answer.lower()
    assert "2.0 unit(s)/day" in response.answer
    assert response.tool_results["stock_velocity"][0]["days_of_stock_remaining"] == 2.0


def test_ai_manager_answers_trend_questions_from_revenue_comparison(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    manager = _manager(db_session, organization.id)
    previous_event = _ingested(
        db_session,
        organization,
        branch_a,
        device_a,
        event_id="77777777-7777-7777-7777-777777777775",
        sequence=6,
        event_type=SyncEventType.SALE_CREATED,
    )
    current_event = _ingested(
        db_session,
        organization,
        branch_a,
        device_a,
        event_id="77777777-7777-7777-7777-777777777776",
        sequence=7,
        event_type=SyncEventType.SALE_CREATED,
    )
    db_session.add_all(
        [
            CloudSaleFact(
                source_event_id=previous_event.id,
                organization_id=organization.id,
                branch_id=branch_a.id,
                source_device_id=device_a.id,
                local_sale_id=1,
                invoice_number="TREND-PREV",
                total_amount=Decimal("200.00"),
                payment_method="cash",
                item_count=1,
                payload={},
                occurred_at=datetime.now(timezone.utc) - timedelta(days=10),
            ),
            CloudSaleFact(
                source_event_id=current_event.id,
                organization_id=organization.id,
                branch_id=branch_a.id,
                source_device_id=device_a.id,
                local_sale_id=2,
                invoice_number="TREND-CUR",
                total_amount=Decimal("50.00"),
                payment_method="cash",
                item_count=1,
                payload={},
                occurred_at=datetime.now(timezone.utc) - timedelta(days=2),
            ),
        ]
    )
    db_session.commit()

    response = chat_with_ai_manager(
        AIManagerChatRequest(
            message="Compare this week with last week and show branch drops",
            organization_id=organization.id,
            period_days=7,
        ),
        db=db_session,
        current_user=manager,
    )

    assert response.refused is False
    assert "highest branch anomaly" in response.answer.lower()
    assert response.tool_results["revenue_comparison"]["anomaly_count"] == 1
    assert response.tool_results["revenue_comparison"]["branches"][0]["status"] == "severe_drop"


def test_ai_manager_answers_reconciliation_questions_from_cloud_checks(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_facts(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id)

    response = chat_with_ai_manager(
        AIManagerChatRequest(
            message="Is the cloud data reliable for decisions?",
            organization_id=organization.id,
        ),
        db=db_session,
        current_user=manager,
    )

    assert response.refused is False
    assert "reconciliation" in response.answer.lower()
    assert response.tool_results["reconciliation"]["issue_count"] >= 1
    assert response.tool_results["reconciliation"]["high_issue_count"] >= 1


@pytest.mark.parametrize("provider", ["openai", "claude", "groq"])
def test_ai_manager_uses_deterministic_without_tenant_external_ai_consent(monkeypatch, db_session, provider):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_facts(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id, username=f"{provider}-manager")
    monkeypatch.setattr(settings, "AI_MANAGER_PROVIDER", provider)
    monkeypatch.setattr(settings, "AI_MANAGER_MODEL", "external-model")

    response = chat_with_ai_manager(
        AIManagerChatRequest(
            message="Summarize sales",
            organization_id=organization.id,
        ),
        db=db_session,
        current_user=manager,
    )

    assert response.provider == "deterministic"
    assert response.model is None
    assert response.fallback_used is False
    assert response.tool_results["sales_summary"]["total_revenue"] == 400.0


def test_admin_can_manage_tenant_external_ai_settings(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    admin = _admin(db_session, organization.id)

    default_setting = get_external_provider_settings(
        organization_id=organization.id,
        db=db_session,
        current_user=admin,
    )
    saved = upsert_external_provider_settings(
        AIExternalProviderSettingUpsert(
            organization_id=organization.id,
            external_ai_enabled=True,
            allowed_providers=["openai", "groq"],
            preferred_provider="groq",
            preferred_model="llama-3.3-70b-versatile",
            consent_text="Owner approved external AI summaries.",
        ),
        db=db_session,
        current_user=admin,
    )

    assert default_setting.external_ai_enabled is False
    assert saved.external_ai_enabled is True
    assert saved.allowed_providers == ["openai", "groq"]
    assert saved.preferred_provider == "groq"
    assert saved.preferred_model == "llama-3.3-70b-versatile"
    assert saved.consented_by_user_id == admin.id
    assert saved.consented_at is not None

    audit_entry = (
        db_session.query(ActivityLog)
        .filter(
            ActivityLog.action == "update_ai_external_provider_policy",
            ActivityLog.organization_id == organization.id,
            ActivityLog.entity_id == saved.id,
        )
        .order_by(ActivityLog.id.desc())
        .first()
    )
    assert audit_entry is not None
    assert audit_entry.user_id == admin.id
    assert audit_entry.extra_data["external_ai_enabled"] is True
    assert audit_entry.extra_data["allowed_providers"] == ["openai", "groq"]


def test_server_configured_external_ai_uses_available_api_key_without_tenant_policy(monkeypatch, db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_facts(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id)
    monkeypatch.setattr(settings, "AI_MANAGER_PROVIDER", "groq")
    monkeypatch.setattr(settings, "AI_MANAGER_MODEL", "")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-groq-key")

    def _fake_tool_answer(*, message, system_prompt, tools, tool_dispatcher, conversation_history, provider, model, fallback_summary):
        return {"answer": "External Groq summary.", "provider": provider, "model": model, "fallback_used": False}

    monkeypatch.setattr(AIManagerLLMProvider, "generate_answer_with_tools", _fake_tool_answer)

    response = chat_with_ai_manager(
        AIManagerChatRequest(
            message="Summarize sales",
            organization_id=organization.id,
        ),
        db=db_session,
        current_user=manager,
    )

    assert response.provider == "groq"
    assert response.model == "llama-3.3-70b-versatile"
    assert response.fallback_used is False
    assert response.answer == "External Groq summary."
    assert response.verification["verified"] is True


def test_external_ai_numeric_claims_are_verified_before_return(monkeypatch, db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_facts(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id, username="verified-ai-manager")
    monkeypatch.setattr(settings, "AI_MANAGER_PROVIDER", "groq")
    monkeypatch.setattr(settings, "AI_MANAGER_MODEL", "")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-groq-key")

    def _fake_wrong_answer(*, message, system_prompt, tools, tool_dispatcher, conversation_history, provider, model, fallback_summary):
        return {
            "answer": "For all branches, revenue is GHS 9999.00.",
            "provider": provider,
            "model": model,
            "fallback_used": False,
            "tool_trace": [
                {
                    "tool": "get_sales_summary",
                    "arguments": {"period": "period"},
                    "result": {"sales_count": 2, "total_revenue": 400.0, "total_items": 13},
                }
            ],
        }

    monkeypatch.setattr(AIManagerLLMProvider, "generate_answer_with_tools", _fake_wrong_answer)

    response = chat_with_ai_manager(
        AIManagerChatRequest(
            message="Summarize sales",
            organization_id=organization.id,
        ),
        db=db_session,
        current_user=manager,
    )

    assert response.fallback_used is True
    assert response.verification["verified"] is False
    assert "GHS 9999.00" in response.verification["unsupported_numbers"]
    assert "9999.00" not in response.answer
    assert response.tool_trace[0]["tool"] == "get_sales_summary"


def test_external_ai_tool_trace_is_returned(monkeypatch, db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_facts(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id, username="trace-ai-manager")
    monkeypatch.setattr(settings, "AI_MANAGER_PROVIDER", "groq")
    monkeypatch.setattr(settings, "AI_MANAGER_MODEL", "")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-groq-key")

    def _fake_trace_answer(*, message, system_prompt, tools, tool_dispatcher, conversation_history, provider, model, fallback_summary):
        result = tool_dispatcher("get_sales_summary", {"period": "period"})
        return {
            "answer": "For all branches in the last 30 day(s), revenue is GHS 400.00 from 2 sale(s).",
            "provider": provider,
            "model": model,
            "fallback_used": False,
            "tool_trace": [{"tool": "get_sales_summary", "arguments": {"period": "period"}, "result": result}],
        }

    monkeypatch.setattr(AIManagerLLMProvider, "generate_answer_with_tools", _fake_trace_answer)

    response = chat_with_ai_manager(
        AIManagerChatRequest(
            message="Summarize sales",
            organization_id=organization.id,
            period_days=30,
        ),
        db=db_session,
        current_user=manager,
    )

    assert response.fallback_used is False
    assert response.verification["verified"] is True
    assert response.tool_trace == [
        {
            "tool": "get_sales_summary",
            "arguments": {"period": "period"},
            "result": {"sales_count": 2, "total_revenue": 400.0, "total_items": 13},
        }
    ]


def test_telegram_ceo_message_routes_to_ai_without_user_context(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_facts(db_session, organization, branch_a, branch_b, device_a, device_b)
    db_session.add(
        AIWeeklyReportDeliverySetting(
            organization_id=organization.id,
            branch_id=None,
            report_scope_key="org",
            telegram_enabled=True,
            telegram_chat_ids=["12345"],
            is_active=True,
        )
    )
    db_session.commit()

    answer = TelegramAlertService.route_ceo_message(
        db_session,
        chat_id="12345",
        text="Summarize sales",
    )

    assert answer is not None
    assert "error occurred" not in answer.lower()
    assert "400.00" in answer


def test_branch_manager_cannot_change_tenant_external_ai_settings(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    branch_manager = _manager(db_session, organization.id, branch_id=branch_a.id, username="branch-ai-policy")

    with pytest.raises(HTTPException) as exc:
        upsert_external_provider_settings(
            AIExternalProviderSettingUpsert(
                organization_id=organization.id,
                external_ai_enabled=True,
                allowed_providers=["openai"],
                preferred_provider="openai",
                preferred_model="gpt-4o-mini",
            ),
            db=db_session,
            current_user=branch_manager,
        )

    assert exc.value.status_code == 403


def test_ai_manager_briefing_returns_findings_for_critical_stock(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_facts(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id, username="briefing-manager")

    event_a = db_session.query(IngestedSyncEvent).filter_by(
        organization_id=organization.id,
        branch_id=branch_a.id,
    ).first()
    db_session.add(
        CloudProductSnapshot(
            organization_id=organization.id,
            branch_id=branch_a.id,
            local_product_id=999,
            name="Empty Syrup",
            sku="EMPTY-1",
            total_stock=0,
            low_stock_threshold=5,
            is_active=True,
            last_source_event_id=event_a.id,
            payload={},
        )
    )
    db_session.commit()

    briefing = get_ai_manager_briefing(
        organization_id=organization.id,
        branch_id=None,
        period_days=30,
        max_findings=5,
        persist=False,
        db=db_session,
        current_user=manager,
    )

    assert briefing.organization_id == organization.id
    assert isinstance(briefing.findings, list)
    assert briefing.data_trust_status in {"ok", "degraded", "unsafe"}
    finding_types = [f.type for f in briefing.findings]
    assert "sync_failure" in finding_types, "Projection failure must be flagged in briefing"


def test_ai_manager_briefing_respects_branch_scope(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_facts(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id, username="briefing-branch-manager")

    briefing_all = get_ai_manager_briefing(
        organization_id=organization.id,
        branch_id=None,
        period_days=30,
        max_findings=5,
        persist=False,
        db=db_session,
        current_user=manager,
    )
    briefing_branch_a = get_ai_manager_briefing(
        organization_id=organization.id,
        branch_id=branch_a.id,
        period_days=30,
        max_findings=5,
        persist=False,
        db=db_session,
        current_user=manager,
    )

    assert briefing_all.branch_id is None
    assert briefing_branch_a.branch_id == branch_a.id


def test_ai_manager_briefing_empty_data_trust_is_unsafe(db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    manager = _manager(db_session, organization.id, username="briefing-empty-manager")

    briefing = get_ai_manager_briefing(
        organization_id=organization.id,
        branch_id=None,
        period_days=30,
        max_findings=5,
        persist=False,
        db=db_session,
        current_user=manager,
    )

    assert briefing.organization_id == organization.id
    assert briefing.data_trust_status in {"unsafe", "degraded"}
    assert len(briefing.findings) > 0, "No-sync finding must be present when no data exists"


def test_ai_findings_persist_saves_and_lists(db_session):
    """persist=True upserts findings into ai_findings; list endpoint returns them."""
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    manager = _manager(db_session, organization.id, username="findings-persist-manager")

    # Generate briefing with persist=True — no sync data means a no_sync finding
    get_ai_manager_briefing(
        organization_id=organization.id,
        branch_id=None,
        period_days=30,
        max_findings=50,
        persist=True,
        db=db_session,
        current_user=manager,
    )

    findings = list_ai_findings(
        organization_id=organization.id,
        branch_id=None,
        status=None,
        limit=50,
        db=db_session,
        current_user=manager,
    )

    assert len(findings) > 0, "At least one finding must be persisted when no sync data exists"
    assert all(f.status == "open" for f in findings)
    assert all(f.organization_id == organization.id for f in findings)


def test_ai_findings_status_update_works(db_session):
    """Updating a finding status (acknowledge, dismiss, resolve) is reflected immediately."""
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    manager = _manager(db_session, organization.id, username="findings-status-manager")

    get_ai_manager_briefing(
        organization_id=organization.id,
        branch_id=None,
        period_days=30,
        max_findings=50,
        persist=True,
        db=db_session,
        current_user=manager,
    )

    findings = list_ai_findings(
        organization_id=organization.id,
        branch_id=None,
        status=None,
        limit=50,
        db=db_session,
        current_user=manager,
    )
    assert findings, "Need at least one finding to test status update"

    target_id = findings[0].id

    updated = update_ai_finding_status(
        finding_id=target_id,
        payload=AIFindingStatusUpdate(status="acknowledged"),
        organization_id=organization.id,
        db=db_session,
        current_user=manager,
    )
    assert updated.id == target_id
    assert updated.status == "acknowledged"

    # Dismiss it
    dismissed = update_ai_finding_status(
        finding_id=target_id,
        payload=AIFindingStatusUpdate(status="dismissed"),
        organization_id=organization.id,
        db=db_session,
        current_user=manager,
    )
    assert dismissed.status == "dismissed"

    # Dismissed finding must not appear in the default (active) list
    active_findings = list_ai_findings(
        organization_id=organization.id,
        branch_id=None,
        status=None,
        limit=50,
        db=db_session,
        current_user=manager,
    )
    assert all(f.id != target_id for f in active_findings), "Dismissed finding must not appear in active list"


def test_ai_findings_upsert_does_not_duplicate(db_session):
    """Running briefing twice with persist=True should not create duplicate rows."""
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    manager = _manager(db_session, organization.id, username="findings-dedup-manager")

    for _ in range(2):
        get_ai_manager_briefing(
            organization_id=organization.id,
            branch_id=None,
            period_days=30,
            max_findings=50,
            persist=True,
            db=db_session,
            current_user=manager,
        )

    findings = list_ai_findings(
        organization_id=organization.id,
        branch_id=None,
        status=None,
        limit=200,
        db=db_session,
        current_user=manager,
    )

    types = [f.type for f in findings]
    assert len(types) == len(set(types)), "Each finding type must appear at most once (no duplicates)"
