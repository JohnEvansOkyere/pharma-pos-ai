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


@router.get("", response_model=List[UserSchema])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    List all users (Admin only).

    Args:
        db: Database session
        current_user: Current authenticated admin user

    Returns:
        List of users
    """
    users = db.query(User).order_by(User.created_at.desc()).all()
    return users


@router.post("", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Create a new user (Admin only).

    Args:
        user_data: User creation data
        db: Database session
        current_user: Current authenticated admin user

    Returns:
        Created user object

    Raises:
        HTTPException: If username or email already exists
    """
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
    current_user: User = Depends(require_admin)
):
    """
    Update a user (Admin only).

    Args:
        user_id: User ID
        user_data: User update data
        db: Database session
        current_user: Current authenticated admin user

    Returns:
        Updated user object

    Raises:
        HTTPException: If user not found
    """
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
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
    current_user: User = Depends(require_admin)
):
    """
    Delete a user (Admin only).

    Args:
        user_id: User ID
        db: Database session
        current_user: Current authenticated admin user

    Raises:
        HTTPException: If user not found or trying to delete self
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

    db.delete(db_user)
    db.commit()
