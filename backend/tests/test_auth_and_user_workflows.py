from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.endpoints.auth import login
from app.api.endpoints.users import create_user, update_user
from app.models import Branch, Organization
from app.models.activity_log import ActivityLog
from app.models.user import UserPermission, UserRole
from app.schemas.user import User as UserSchema, UserCreate, UserUpdate
from app.api.dependencies.auth import require_adjust_stock, require_manage_products


def test_login_trims_username_and_returns_bearer_token(db_session, admin_user):
    result = login(
        form_data=SimpleNamespace(username="  admin  ", password="admin-secret"),
        db=db_session,
    )

    assert result["token_type"] == "bearer"
    assert result["access_token"]


def test_manager_cannot_create_manager_user(db_session, manager_user):
    with pytest.raises(HTTPException) as exc:
        create_user(
            UserCreate(
                username="newmanager",
                email="newmanager@example.com",
                full_name="New Manager",
                password="secret123",
                role=UserRole.MANAGER,
                is_active=True,
            ),
            db=db_session,
            current_user=manager_user,
        )

    assert exc.value.status_code == 403
    assert "cashier" in exc.value.detail.lower()


def test_admin_can_update_username_and_audit_is_recorded(db_session, admin_user, cashier_user):
    updated = update_user(
        cashier_user.id,
        UserUpdate(username="cashier-renamed"),
        db=db_session,
        current_user=admin_user,
    )

    audit_entry = (
        db_session.query(ActivityLog)
        .filter(ActivityLog.action == "update_user", ActivityLog.entity_id == cashier_user.id)
        .order_by(ActivityLog.id.desc())
        .first()
    )

    assert updated.username == "cashier-renamed"
    assert audit_entry is not None
    assert audit_entry.extra_data["username_updated"] is True


def test_role_default_permissions_allow_existing_managers(manager_user):
    assert require_adjust_stock(current_user=manager_user) == manager_user


def test_explicit_permissions_override_role_defaults(manager_user):
    manager_user.permissions = [UserPermission.ADJUST_STOCK.value]

    assert require_adjust_stock(current_user=manager_user) == manager_user
    with pytest.raises(HTTPException) as exc:
        require_manage_products(current_user=manager_user)

    assert exc.value.status_code == 403
    assert UserPermission.MANAGE_PRODUCTS.value in exc.value.detail


def test_user_schema_exposes_tenant_assignment(db_session, manager_user):
    organization = Organization(name="Schema Tenant")
    db_session.add(organization)
    db_session.flush()
    branch = Branch(organization_id=organization.id, name="Main", code="MAIN")
    db_session.add(branch)
    db_session.flush()
    manager_user.organization_id = organization.id
    manager_user.branch_id = branch.id
    db_session.commit()
    db_session.refresh(manager_user)

    payload = UserSchema.model_validate(manager_user)

    assert payload.organization_id == organization.id
    assert payload.branch_id == branch.id
