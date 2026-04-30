from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.api.endpoints.system_ops import export_audit_logs_csv, get_audit_integrity, list_audit_logs
from app.core.security import get_password_hash
from app.models import Branch, Organization
from app.models.activity_log import ActivityLog
from app.models.user import User, UserRole
from app.services.audit_service import AuditService


def _tenant(db_session, name: str):
    organization = Organization(name=name)
    db_session.add(organization)
    db_session.flush()
    branch = Branch(organization_id=organization.id, name=f"{name} Main", code=name[:4].upper())
    db_session.add(branch)
    db_session.commit()
    return organization, branch


def _admin(db_session, organization_id: int, *, username: str, branch_id=None):
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("admin-secret"),
        full_name="Audit Admin",
        role=UserRole.ADMIN,
        organization_id=organization_id,
        branch_id=branch_id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _manager(db_session, organization_id: int, *, username: str):
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("manager-secret"),
        full_name="Audit Manager",
        role=UserRole.MANAGER,
        organization_id=organization_id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _audit(db_session, *, organization_id: int, branch_id: int, user_id: int | None, action: str):
    entry = ActivityLog(
        organization_id=organization_id,
        branch_id=branch_id,
        user_id=user_id,
        action=action,
        entity_type="ai_weekly_manager_report",
        entity_id=42,
        description=f"{action} description",
        extra_data={"status": "sent", "action": action},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(entry)
    db_session.commit()
    return entry


def test_admin_lists_tenant_scoped_audit_logs_with_filters(db_session):
    organization, branch = _tenant(db_session, "Audit Tenant")
    other_organization, other_branch = _tenant(db_session, "Other Tenant")
    admin = _admin(db_session, organization.id, username="audit-admin")
    delivery_entry = _audit(
        db_session,
        organization_id=organization.id,
        branch_id=branch.id,
        user_id=admin.id,
        action="create_ai_weekly_report_delivery",
    )
    _audit(
        db_session,
        organization_id=organization.id,
        branch_id=branch.id,
        user_id=admin.id,
        action="review_ai_weekly_report",
    )
    _audit(
        db_session,
        organization_id=other_organization.id,
        branch_id=other_branch.id,
        user_id=None,
        action="create_ai_weekly_report_delivery",
    )

    result = list_audit_logs(
        organization_id=organization.id,
        branch_id=branch.id,
        action="create_ai_weekly_report_delivery",
        entity_type=None,
        user_id=None,
        start_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        end_at=None,
        limit=20,
        offset=0,
        db=db_session,
        current_user=admin,
    )

    assert result.total == 1
    assert result.items[0].id == delivery_entry.id
    assert result.items[0].organization_id == organization.id
    assert result.items[0].branch_id == branch.id
    assert result.items[0].extra_data["status"] == "sent"


def test_admin_cannot_list_cross_tenant_audit_logs(db_session):
    organization, branch = _tenant(db_session, "Scoped Tenant")
    other_organization, _other_branch = _tenant(db_session, "Blocked Tenant")
    admin = _admin(db_session, organization.id, username="scoped-audit-admin")

    with pytest.raises(HTTPException) as exc:
        list_audit_logs(
            organization_id=other_organization.id,
            branch_id=None,
            action=None,
            entity_type=None,
            user_id=None,
            start_at=None,
            end_at=None,
            limit=20,
            offset=0,
            db=db_session,
            current_user=admin,
        )

    assert exc.value.status_code == 403
    assert "Organization access denied" in exc.value.detail


def test_non_admin_cannot_list_audit_logs_by_direct_call(db_session):
    organization, _branch = _tenant(db_session, "Manager Tenant")
    manager = _manager(db_session, organization.id, username="audit-manager")

    with pytest.raises(HTTPException) as exc:
        list_audit_logs(
            organization_id=organization.id,
            branch_id=None,
            action=None,
            entity_type=None,
            user_id=None,
            start_at=None,
            end_at=None,
            limit=20,
            offset=0,
            db=db_session,
            current_user=manager,
        )

    assert exc.value.status_code == 403


def test_admin_exports_tenant_scoped_audit_logs_csv(db_session):
    organization, branch = _tenant(db_session, "Export Tenant")
    admin = _admin(db_session, organization.id, username="export-audit-admin")
    _audit(
        db_session,
        organization_id=organization.id,
        branch_id=branch.id,
        user_id=admin.id,
        action="review_ai_weekly_report",
    )

    response = export_audit_logs_csv(
        organization_id=organization.id,
        branch_id=None,
        action="review_ai_weekly_report",
        entity_type=None,
        user_id=None,
        start_at=None,
        end_at=None,
        limit=100,
        db=db_session,
        current_user=admin,
    )
    body = response.body.decode("utf-8")

    assert response.media_type == "text/csv"
    assert "review_ai_weekly_report" in body
    assert "ai_weekly_manager_report" in body
    assert "Export Tenant" not in body


def test_admin_verifies_valid_tenant_audit_hash_chain(db_session):
    organization, branch = _tenant(db_session, "Integrity Tenant")
    admin = _admin(db_session, organization.id, username="integrity-admin")
    first = AuditService.log(
        db_session,
        organization_id=organization.id,
        branch_id=branch.id,
        user_id=admin.id,
        action="create_stock_adjustment",
        entity_type="stock_adjustment",
        entity_id=10,
        description="Recorded adjustment",
        extra_data={"quantity": 4},
    )
    second = AuditService.log(
        db_session,
        organization_id=organization.id,
        branch_id=branch.id,
        user_id=admin.id,
        action="repair_cloud_reconciliation_issue",
        entity_type="cloud_reconciliation_repair",
        entity_id=None,
        description="Ran repair",
        extra_data={"repair_type": "retry_failed_projections"},
    )
    db_session.commit()

    result = get_audit_integrity(
        organization_id=organization.id,
        db=db_session,
        current_user=admin,
    )

    assert result.valid is True
    assert result.total_count == 2
    assert result.sealed_count == 2
    assert result.unsealed_count == 0
    assert first.previous_hash == AuditService.GENESIS_HASH
    assert second.previous_hash == first.current_hash
    assert len(second.current_hash) == 64


def test_admin_detects_tampered_audit_payload(db_session):
    organization, branch = _tenant(db_session, "Tamper Tenant")
    admin = _admin(db_session, organization.id, username="tamper-admin")
    entry = AuditService.log(
        db_session,
        organization_id=organization.id,
        branch_id=branch.id,
        user_id=admin.id,
        action="review_ai_weekly_report",
        entity_type="ai_weekly_manager_report",
        entity_id=55,
        description="Reviewed report",
        extra_data={"notes_present": True},
    )
    db_session.commit()

    entry.extra_data = {"notes_present": False}
    db_session.commit()

    result = get_audit_integrity(
        organization_id=organization.id,
        db=db_session,
        current_user=admin,
    )

    assert result.valid is False
    assert result.first_invalid_log_id == entry.id
    assert result.issues[0].issue_type == "current_hash_mismatch"


def test_admin_detects_unsealed_audit_row_after_chain_started(db_session):
    organization, branch = _tenant(db_session, "Unsealed Tenant")
    admin = _admin(db_session, organization.id, username="unsealed-admin")
    AuditService.log(
        db_session,
        organization_id=organization.id,
        branch_id=branch.id,
        user_id=admin.id,
        action="update_ai_external_provider_policy",
        entity_type="ai_external_provider_setting",
        entity_id=3,
        description="Updated policy",
        extra_data={"external_ai_enabled": True},
    )
    db_session.commit()
    _audit(
        db_session,
        organization_id=organization.id,
        branch_id=branch.id,
        user_id=admin.id,
        action="manual_unsealed_insert",
    )

    result = get_audit_integrity(
        organization_id=organization.id,
        db=db_session,
        current_user=admin,
    )

    assert result.valid is False
    assert result.unsealed_after_chain_count == 1
    assert result.issues[0].issue_type == "unsealed_after_chain_started"
