from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.api.endpoints.system_ops import export_audit_logs_csv, list_audit_logs
from app.core.security import get_password_hash
from app.models import Branch, Organization
from app.models.activity_log import ActivityLog
from app.models.user import User, UserRole


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
