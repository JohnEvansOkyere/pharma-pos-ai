"""
Authentication API endpoints.
"""
import time
import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import verify_password, create_access_token, get_password_hash
from app.db.base import get_db
from app.models.user import User
from app.schemas.user import Token, User as UserSchema
from app.api.dependencies import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# ── In-memory login rate limiter ──────────────────────────────────────────────
# Suitable for single-process local pharmacy deployments. For multi-process
# setups, swap to Redis-backed storage.
_login_attempts: dict[str, list[float]] = defaultdict(list)
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300  # 5 minutes

# Pre-computed dummy hash so that timing is constant when a user is not found.
_DUMMY_HASH = get_password_hash("__dummy_never_match_placeholder__")


def _check_rate_limit(username: str) -> None:
    """Reject if too many recent failed login attempts for this username."""
    now = time.time()
    attempts = _login_attempts[username]
    # Prune expired entries
    _login_attempts[username] = [t for t in attempts if now - t < _WINDOW_SECONDS]
    if len(_login_attempts[username]) >= _MAX_ATTEMPTS:
        logger.warning("Login rate limit exceeded for username=%s", username)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Try again in {_WINDOW_SECONDS // 60} minutes.",
        )


def _record_failed_attempt(username: str) -> None:
    _login_attempts[username].append(time.time())


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
        HTTPException: If credentials are invalid or rate limited
    """
    normalized_username = form_data.username.strip()

    # Rate-limit check (P1-07)
    _check_rate_limit(normalized_username)

    # Find user by username
    user = db.query(User).filter(User.username == normalized_username).first()

    if not user:
        # Always run bcrypt to prevent timing-based username enumeration (P3-01)
        verify_password("__dummy__", _DUMMY_HASH)
        _record_failed_attempt(normalized_username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(form_data.password, user.hashed_password):
        _record_failed_attempt(normalized_username)
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


@router.get("/heartbeat")
def heartbeat(current_user: User = Depends(get_current_active_user)):
    """
    Lightweight connectivity probe used by the frontend online-status hook.

    Returns 200 when the backend is reachable and the token is valid.
    Called every 15 seconds when the hosted browser queue is enabled.
    """
    return {"status": "ok", "user_id": current_user.id}


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
