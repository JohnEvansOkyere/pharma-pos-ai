"""
Authentication API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import verify_password, create_access_token
from app.db.base import get_db
from app.models.user import User
from app.schemas.user import Token, User as UserSchema
from app.api.dependencies import get_current_active_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    User login endpoint.

    Args:
        form_data: OAuth2 form with username and password
        db: Database session

    Returns:
        JWT access token

    Raises:
        HTTPException: If credentials are invalid
    """
    normalized_username = form_data.username.strip()

    # Find user by username
    user = db.query(User).filter(User.username == normalized_username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    # Create access token
    access_token = create_access_token(data={"user_id": user.id, "username": user.username})

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserSchema)
def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current logged-in user information.

    Args:
        current_user: Current authenticated user

    Returns:
        User object
    """
    return current_user
