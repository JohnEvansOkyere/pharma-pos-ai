"""
Application mode helpers.

The same codebase can run in three modes:

- ``local_pos``        — offline-first pharmacy installation (local PostgreSQL)
- ``online_pos``       — online-first pharmacy installation (cloud Supabase DB,
                         full POS writes, customer retention features enabled)
- ``cloud_reporting``  — vendor reporting portal (read-only, no POS writes)

Cloud reporting mode must not behave like a second till.
``online_pos`` mode behaves identically to ``local_pos`` for POS write
operations but skips the sync outbox (writes go directly to the cloud DB).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable

from fastapi import HTTPException, status

if TYPE_CHECKING:
    # Imported only for type hints — avoids circular import at runtime.
    from app.models.user import User


LOCAL_POS_MODE = "local_pos"
ONLINE_POS_MODE = "online_pos"
CLOUD_REPORTING_MODE = "cloud_reporting"
VALID_APP_MODES = {LOCAL_POS_MODE, ONLINE_POS_MODE, CLOUD_REPORTING_MODE}

SAFE_HTTP_METHODS = {"GET", "HEAD", "OPTIONS"}

LOCAL_OPERATIONAL_PREFIXES: tuple[str, ...] = (
    "/api/products",
    "/api/categories",
    "/api/suppliers",
    "/api/sales",
    "/api/stock-adjustments",
    "/api/stock-takes",
    "/api/notifications",
    "/api/system",
)


def normalize_app_mode(value: str | None) -> str:
    mode = (value or LOCAL_POS_MODE).strip().lower()
    if mode not in VALID_APP_MODES:
        return LOCAL_POS_MODE
    return mode


def is_cloud_reporting_mode(value: str | None) -> bool:
    return normalize_app_mode(value) == CLOUD_REPORTING_MODE


def is_online_pos_mode(value: str | None) -> bool:
    """True when the app is an online-first POS (city pharmacy)."""
    return normalize_app_mode(value) == ONLINE_POS_MODE


def is_pos_mode(value: str | None) -> bool:
    """True when POS write operations are allowed (local_pos or online_pos)."""
    return normalize_app_mode(value) in {LOCAL_POS_MODE, ONLINE_POS_MODE}


def is_local_operational_write(
    *,
    app_mode: str | None,
    method: str,
    path: str,
    prefixes: Iterable[str] = LOCAL_OPERATIONAL_PREFIXES,
) -> bool:
    if not is_cloud_reporting_mode(app_mode):
        return False

    if method.upper() in SAFE_HTTP_METHODS:
        return False

    normalized_path = path.rstrip("/") or "/"
    for prefix in prefixes:
        if normalized_path == prefix or normalized_path.startswith(f"{prefix}/"):
            return True

    return False


def apply_tenant_scope(obj: Any, current_user: "User", *, app_mode: str | None) -> None:
    """Stamp ``organization_id`` and ``branch_id`` from the authenticated user
    onto an ORM object in ``online_pos`` mode.

    In ``local_pos`` mode this is a no-op — tenancy is supplied through the
    sync configuration (``CLOUD_SYNC_ORGANIZATION_ID`` / ``CLOUD_SYNC_BRANCH_ID``).
    In ``online_pos`` mode every POS write must be scoped to the tenant of the
    user making the request so that rows from different city pharmacies sharing
    the same cloud database cannot bleed across organization boundaries.

    Call this before ``db.add()`` / ``db.flush()`` so scope is present on the
    first INSERT.

    Usage::

        apply_tenant_scope(db_sale, current_user, app_mode=settings.APP_MODE)
    """
    if not is_online_pos_mode(app_mode):
        return

    if current_user.organization_id is not None:
        obj.organization_id = current_user.organization_id

    if current_user.branch_id is not None:
        obj.branch_id = current_user.branch_id


def require_online_tenant_scope(current_user: "User", *, app_mode: str | None) -> None:
    """Reject online POS writes from vendor or incompletely provisioned users."""
    if not is_online_pos_mode(app_mode):
        return

    if current_user.organization_id is None or current_user.branch_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Online POS user must be assigned to an organization and branch",
        )


def scope_query_to_user(
    query,
    model: Any,
    current_user: "User",
    *,
    app_mode: str | None,
    include_branch: bool = True,
):
    """Apply organization and optional branch ownership to an ORM query."""
    organization_id = getattr(current_user, "organization_id", None)
    branch_id = getattr(current_user, "branch_id", None)

    if organization_id is None:
        if is_online_pos_mode(app_mode):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Online POS user must be assigned to an organization",
            )
        return query

    if hasattr(model, "organization_id"):
        query = query.filter(model.organization_id == organization_id)
    if include_branch and branch_id is not None and hasattr(model, "branch_id"):
        query = query.filter(model.branch_id == branch_id)
    return query
