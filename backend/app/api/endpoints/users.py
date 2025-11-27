"""
User management API endpoints (Admin only).
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.user import User, UserRole
from app.schemas.user import User as UserSchema, UserCreate, UserUpdate
from app.api.dependencies import get_current_active_user
from app.core.security import get_password_hash

router = APIRouter(prefix="/users", tags=["Users"])


def require_admin(current_user: User = Depends(get_current_active_user)):
    """
    Dependency to check if current user is admin.

    Args:
        current_user: Current authenticated user

    Returns:
        User object if admin

    Raises:
        HTTPException: If user is not admin
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_admin_or_manager(current_user: User = Depends(get_current_active_user)):
    """
    Dependency to check if current user is admin or manager.

    Args:
        current_user: Current authenticated user

    Returns:
        User object if admin or manager

    Raises:
        HTTPException: If user is not admin or manager
    """
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Manager access required"
        )
    return current_user


@router.get("", response_model=List[UserSchema])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_manager)
):
    """
    List all users (Admin or Manager).

    Args:
        db: Database session
        current_user: Current authenticated admin or manager user

    Returns:
        List of users
    """
    users = db.query(User).order_by(User.created_at.desc()).all()
    return users


@router.post("", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_manager)
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
    # Managers can only create cashiers
    if current_user.role == UserRole.MANAGER:
        if user_data.role != UserRole.CASHIER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers can only create cashier users"
            )

    # Check if username exists
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if email exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hashed_password,
        role=user_data.role,
        is_active=user_data.is_active if user_data.is_active is not None else True,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@router.put("/{user_id}", response_model=UserSchema)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_manager)
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
    db_user = db.query(User).filter(User.id == user_id).first()
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
    if user_data.email is not None:
        # Check if email is already taken by another user
        existing = db.query(User).filter(
            User.email == user_data.email,
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        db_user.email = user_data.email

    if user_data.full_name is not None:
        db_user.full_name = user_data.full_name

    if user_data.role is not None:
        db_user.role = user_data.role

    if user_data.is_active is not None:
        db_user.is_active = user_data.is_active

    if user_data.password is not None:
        db_user.hashed_password = get_password_hash(user_data.password)

    db.commit()
    db.refresh(db_user)

    return db_user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_manager)
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

    db_user = db.query(User).filter(User.id == user_id).first()
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

    db.delete(db_user)
    db.commit()
