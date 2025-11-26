"""
API dependencies package.
"""
from app.api.dependencies.auth import (
    get_current_user,
    get_current_active_user,
    require_admin,
    require_manager,
    require_role,
)

__all__ = [
    "get_current_user",
    "get_current_active_user",
    "require_admin",
    "require_manager",
    "require_role",
]
