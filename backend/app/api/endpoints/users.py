"""
User management API endpoints (Admin only).
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.user import User, UserRole
from app.models.sync_event import SyncEventType
from app.schemas.user import User as UserSchema, UserCreate, UserUpdate
from app.api.dependencies import get_current_active_user, require_manage_users
from app.core.app_mode import apply_tenant_scope, scope_query_to_user
from app.core.config import settings
from app.core.security import get_password_hash
from app.services.audit_service import AuditService
from app.services.sync_outbox_service import SyncOutboxService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=List[UserSchema])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manage_users)
):
    """
    List all users (Admin or Manager).

    Args:
        db: Database session
        current_user: Current authenticated admin or manager user

    Returns:
        List of users
    """
    users = scope_query_to_user(
        db.query(User),
        User,
        current_user,
        app_mode=settings.APP_MODE,
    ).order_by(User.created_at.desc()).all()
    return users


@router.post("", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manage_users)
):
    """
    Create a new user (Admin or Manager).

    Managers can only create cashier users.
    Admins can create users with any role.

    Args:
        user_data: User creation data
        db: Database session
        current_user: Current authenticated admin or manager user

    Returns:
        Created user object

    Raises:
        HTTPException: If username or email already exists, or if manager tries to create non-cashier
    """
    normalized_username = user_data.username.strip()
    normalized_email = user_data.email.strip().lower()
    normalized_full_name = user_data.full_name.strip()

    # Managers can only create cashiers
    if current_user.role == UserRole.MANAGER:
        if user_data.role != UserRole.CASHIER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers can only create cashier users"
            )

    # Check if username exists
    organization_users = scope_query_to_user(
        db.query(User),
        User,
        current_user,
        app_mode=settings.APP_MODE,
        include_branch=False,
    )
    if organization_users.filter(User.username == normalized_username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if email exists
    if organization_users.filter(User.email == normalized_email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=normalized_username,
        email=normalized_email,
        full_name=normalized_full_name,
        hashed_password=hashed_password,
        role=user_data.role,
        permissions=[permission.value for permission in user_data.permissions] if user_data.permissions is not None else None,
        is_active=user_data.is_active if user_data.is_active is not None else True,
    )

    apply_tenant_scope(db_user, current_user, app_mode=settings.APP_MODE)
    db.add(db_user)
    db.flush()
    SyncOutboxService.record_event(
        db,
        event_type=SyncEventType.USER_CREATED,
        aggregate_type="user",
        aggregate_id=db_user.id,
        organization_id=db_user.organization_id,
        branch_id=db_user.branch_id,
        payload={
            "user_id": db_user.id,
            "username": db_user.username,
            "email": db_user.email,
            "role": db_user.role.value,
            "permissions": db_user.permissions,
            "is_active": db_user.is_active,
        },
    )
    AuditService.log(
        db,
        action="create_user",
        user_id=current_user.id,
        entity_type="user",
        entity_id=db_user.id,
        description=f"Created user {db_user.username}",
        extra_data={"role": db_user.role.value, "is_active": db_user.is_active},
        organization_id=db_user.organization_id,
        branch_id=db_user.branch_id,
    )
    db.commit()
    db.refresh(db_user)

    return db_user


@router.put("/{user_id}", response_model=UserSchema)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manage_users)
):
    """
    Update a user (Admin or Manager).

    Managers can only update cashier users and cannot change roles.
    Admins can update any user and change roles.

    Args:
        user_id: User ID
        user_data: User update data
        db: Database session
        current_user: Current authenticated admin or manager user

    Returns:
        Updated user object

    Raises:
        HTTPException: If user not found or manager tries to update non-cashier
    """
    normalized_username = user_data.username.strip() if user_data.username is not None else None
    normalized_email = user_data.email.strip().lower() if user_data.email is not None else None
    normalized_full_name = user_data.full_name.strip() if user_data.full_name is not None else None

    scoped_users = scope_query_to_user(
        db.query(User),
        User,
        current_user,
        app_mode=settings.APP_MODE,
    )
    db_user = scoped_users.filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Managers can only update cashiers and cannot change roles
    if current_user.role == UserRole.MANAGER:
        if db_user.role != UserRole.CASHIER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers can only update cashier users"
            )
        if user_data.role is not None and user_data.role != UserRole.CASHIER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers cannot change user roles"
            )

    # Update fields
    if normalized_username is not None:
        existing = scope_query_to_user(
            db.query(User),
            User,
            current_user,
            app_mode=settings.APP_MODE,
            include_branch=False,
        ).filter(
            User.username == normalized_username,
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        db_user.username = normalized_username

    if normalized_email is not None:
        # Check if email is already taken by another user
        existing = scope_query_to_user(
            db.query(User),
            User,
            current_user,
            app_mode=settings.APP_MODE,
            include_branch=False,
        ).filter(
            User.email == normalized_email,
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        db_user.email = normalized_email

    if normalized_full_name is not None:
        db_user.full_name = normalized_full_name

    if user_data.role is not None:
        db_user.role = user_data.role

    if user_data.permissions is not None:
        db_user.permissions = [permission.value for permission in user_data.permissions]

    if user_data.is_active is not None:
        db_user.is_active = user_data.is_active

    if user_data.password is not None:
        db_user.hashed_password = get_password_hash(user_data.password)

    SyncOutboxService.record_event(
        db,
        event_type=SyncEventType.USER_UPDATED,
        aggregate_type="user",
        aggregate_id=db_user.id,
        organization_id=db_user.organization_id,
        branch_id=db_user.branch_id,
        payload={
            "user_id": db_user.id,
            "updated_fields": sorted(user_data.model_dump(exclude_unset=True).keys()),
            "role": db_user.role.value,
            "permissions": db_user.permissions,
            "is_active": db_user.is_active,
            "password_updated": user_data.password is not None,
        },
    )
    AuditService.log(
        db,
        action="update_user",
        user_id=current_user.id,
        entity_type="user",
        entity_id=db_user.id,
        description=f"Updated user {db_user.username}",
        extra_data={
            "username_updated": normalized_username is not None,
            "email_updated": normalized_email is not None,
            "role": db_user.role.value,
            "is_active": db_user.is_active,
            "password_updated": user_data.password is not None,
        },
        organization_id=db_user.organization_id,
        branch_id=db_user.branch_id,
    )
    db.commit()
    db.refresh(db_user)

    return db_user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manage_users)
):
    """
    Delete a user (Admin or Manager).

    Managers can only delete cashier users.
    Admins can delete any user.

    Args:
        user_id: User ID
        db: Database session
        current_user: Current authenticated admin or manager user

    Raises:
        HTTPException: If user not found, trying to delete self, or manager tries to delete non-cashier
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    db_user = scope_query_to_user(
        db.query(User),
        User,
        current_user,
        app_mode=settings.APP_MODE,
    ).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Managers can only delete cashiers
    if current_user.role == UserRole.MANAGER:
        if db_user.role != UserRole.CASHIER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers can only delete cashier users"
            )

    # Soft-delete: deactivate the user and clear credentials.
    # Sales, audit logs, and inventory movements are preserved for
    # financial and regulatory traceability.
    db_user.is_active = False
    db_user.hashed_password = "DEACTIVATED"

    SyncOutboxService.record_event(
        db,
        event_type=SyncEventType.USER_DELETED,
        aggregate_type="user",
        aggregate_id=db_user.id,
        organization_id=db_user.organization_id,
        branch_id=db_user.branch_id,
        payload={
            "user_id": db_user.id,
            "username": db_user.username,
            "role": db_user.role.value,
            "action": "soft_delete",
        },
    )
    AuditService.log(
        db,
        action="deactivate_user",
        user_id=current_user.id,
        entity_type="user",
        entity_id=db_user.id,
        description=f"Deactivated user {db_user.username} (soft-delete)",
        extra_data={"role": db_user.role.value},
        organization_id=db_user.organization_id,
        branch_id=db_user.branch_id,
    )
    db.commit()
