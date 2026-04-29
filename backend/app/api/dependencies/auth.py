"""
Authentication dependencies for FastAPI endpoints.
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.base import get_db
from app.models.user import User, UserPermission, UserRole

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from JWT token.

    Args:
        token: JWT access token
        db: Database session

    Returns:
        Current user object

    Raises:
        HTTPException: If user not found or inactive
    """
    payload = decode_access_token(token)
    user_id: Optional[int] = payload.get("user_id")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current active user.

    Args:
        current_user: Current user from token

    Returns:
        Active user object
    """
    return current_user


def require_role(required_role: UserRole):
    """
    Dependency factory to require a specific role.

    Args:
        required_role: Required user role

    Returns:
        Dependency function that validates user role
    """
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        """Check if user has required role."""
        role_hierarchy = {
            UserRole.CASHIER: 1,
            UserRole.MANAGER: 2,
            UserRole.ADMIN: 3,
        }

        if role_hierarchy[current_user.role] < role_hierarchy[required_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_checker


def require_permission(required_permission: UserPermission):
    """
    Dependency factory to require a granular permission.

    Users with explicit permissions use that list. Existing users without an
    explicit list fall back to role defaults.
    """
    def permission_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if required_permission.value not in current_user.effective_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {required_permission.value}",
            )
        return current_user

    return permission_checker


# Convenience dependencies
require_admin = require_role(UserRole.ADMIN)
require_manager = require_role(UserRole.MANAGER)
require_manage_products = require_permission(UserPermission.MANAGE_PRODUCTS)
require_manage_suppliers = require_permission(UserPermission.MANAGE_SUPPLIERS)
require_manage_categories = require_permission(UserPermission.MANAGE_CATEGORIES)
require_manage_users = require_permission(UserPermission.MANAGE_USERS)
require_view_reports = require_permission(UserPermission.VIEW_REPORTS)
require_void_sale = require_permission(UserPermission.VOID_SALE)
require_refund_sale = require_permission(UserPermission.REFUND_SALE)
require_adjust_stock = require_permission(UserPermission.ADJUST_STOCK)
require_perform_stock_take = require_permission(UserPermission.PERFORM_STOCK_TAKE)
require_trigger_backup = require_permission(UserPermission.TRIGGER_BACKUP)
