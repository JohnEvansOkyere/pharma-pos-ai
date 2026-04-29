from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.api.endpoints.ai_manager import chat_with_ai_manager
from app.core.config import settings
from app.core.security import get_password_hash
from app.models import Branch, Device, Organization
from app.models.cloud_projection import CloudInventoryMovementFact, CloudSaleFact
from app.models.sync_event import SyncEventType
from app.models.sync_ingestion import IngestedSyncEvent
from app.models.tenancy import DeviceStatus
from app.models.user import User, UserPermission, UserRole
from app.schemas.ai_manager import AIManagerChatRequest


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


@pytest.mark.parametrize("provider", ["openai", "claude", "groq"])
def test_ai_manager_supports_configured_external_providers_with_fallback(monkeypatch, db_session, provider):
    organization, branch_a, branch_b, device_a, device_b = _tenant(db_session)
    _seed_facts(db_session, organization, branch_a, branch_b, device_a, device_b)
    manager = _manager(db_session, organization.id, username=f"{provider}-manager")
    monkeypatch.setattr(settings, "AI_MANAGER_PROVIDER", provider)
    monkeypatch.setattr(settings, "AI_MANAGER_MODEL", None)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(settings, "GROQ_API_KEY", None)

    response = chat_with_ai_manager(
        AIManagerChatRequest(
            message="Summarize sales",
            organization_id=organization.id,
        ),
        db=db_session,
        current_user=manager,
    )

    assert response.provider == provider
    assert response.model is None
    assert response.fallback_used is True
    assert response.tool_results["sales_summary"]["total_revenue"] == 400.0
