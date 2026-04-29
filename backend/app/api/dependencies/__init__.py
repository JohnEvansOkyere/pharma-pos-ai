"""
API dependencies package.
"""
from app.api.dependencies.auth import (
    get_current_user,
    get_current_active_user,
    require_admin,
    require_adjust_stock,
    require_manage_categories,
    require_manage_products,
    require_manage_suppliers,
    require_manage_users,
    require_manager,
    require_perform_stock_take,
    require_permission,
    require_refund_sale,
    require_role,
    require_trigger_backup,
    require_view_reports,
    require_void_sale,
)

__all__ = [
    "get_current_user",
    "get_current_active_user",
    "require_admin",
    "require_adjust_stock",
    "require_manage_categories",
    "require_manage_products",
    "require_manage_suppliers",
    "require_manage_users",
    "require_manager",
    "require_perform_stock_take",
    "require_permission",
    "require_refund_sale",
    "require_role",
    "require_trigger_backup",
    "require_view_reports",
    "require_void_sale",
]
