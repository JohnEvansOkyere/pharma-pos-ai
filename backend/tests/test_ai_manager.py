from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.api.endpoints.ai_manager import chat_with_ai_manager, get_external_provider_settings, upsert_external_provider_settings
from app.core.config import settings
from app.core.security import get_password_hash
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
from app.schemas.ai_manager import AIExternalProviderSettingUpsert, AIManagerChatRequest


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
        payload_hash=str(sequence) * 64,
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
    assert f"branch {branch_b.id}" in response.answer.lower()
    assert response.data_scope.organization_id == organization.id
    assert response.data_scope.branch_id is None
    assert response.tool_results["sales_summary"]["total_revenue"] == 400.0
    assert response.tool_results["sync_health"]["projection_failed_count"] == 1


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


def test_enabled_tenant_external_ai_uses_allowed_provider_fallback(monkeypatch, db_session):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_facts(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id)
    admin = _admin(db_session, organization.id)
    monkeypatch.setattr(settings, "GROQ_API_KEY", None)

    upsert_external_provider_settings(
        AIExternalProviderSettingUpsert(
            organization_id=organization.id,
            external_ai_enabled=True,
            allowed_providers=["groq"],
            preferred_provider="groq",
            preferred_model="llama-3.3-70b-versatile",
        ),
        db=db_session,
        current_user=admin,
    )

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
    assert response.fallback_used is True


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
