"""
Application mode and deployment-profile helpers.

The canonical runtime modes are:

- ``operational_pos`` — pharmacy operations against that pharmacy's database
- ``cloud_reporting`` — vendor reporting portal (read-only, no POS writes)

``local_pos`` and ``online_pos`` remain temporary configuration aliases for
``operational_pos``. Hosted/offline differences are deployment features, not
different tenancy models.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable

from fastapi import HTTPException, status

if TYPE_CHECKING:
    # Imported only for type hints — avoids circular import at runtime.
    from app.models.user import User


OPERATIONAL_POS_MODE = "operational_pos"
CLOUD_REPORTING_MODE = "cloud_reporting"
LEGACY_LOCAL_POS_MODE = "local_pos"
LEGACY_ONLINE_POS_MODE = "online_pos"
VALID_APP_MODES = {
    OPERATIONAL_POS_MODE,
    CLOUD_REPORTING_MODE,
    LEGACY_LOCAL_POS_MODE,
    LEGACY_ONLINE_POS_MODE,
}

OFFLINE_DEPLOYMENT = "offline"
HOSTED_DEPLOYMENT = "hosted"
VALID_DEPLOYMENT_PROFILES = {OFFLINE_DEPLOYMENT, HOSTED_DEPLOYMENT}

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
    mode = (value or OPERATIONAL_POS_MODE).strip().lower()
    if mode not in VALID_APP_MODES:
        return OPERATIONAL_POS_MODE
    if mode in {LEGACY_LOCAL_POS_MODE, LEGACY_ONLINE_POS_MODE}:
        return OPERATIONAL_POS_MODE
    return mode


def is_cloud_reporting_mode(value: str | None) -> bool:
    return normalize_app_mode(value) == CLOUD_REPORTING_MODE


def is_pos_mode(value: str | None) -> bool:
    """True when pharmacy operational writes are allowed."""
    return normalize_app_mode(value) == OPERATIONAL_POS_MODE


def is_hosted_deployment(
    deployment_profile: str | None = None,
    *,
    app_mode: str | None = None,
) -> bool:
    """Return whether the operational deployment is hosted."""
    raw_mode = (app_mode or "").strip().lower()
    if raw_mode == LEGACY_ONLINE_POS_MODE:
        return True

    profile = (deployment_profile or "").strip().lower()
    if not profile:
        try:
            from app.core.config import settings

            profile = settings.POS_DEPLOYMENT_PROFILE
        except Exception:
            profile = OFFLINE_DEPLOYMENT
    return profile == HOSTED_DEPLOYMENT


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
    """Stamp available user organization/branch scope on operational writes.

    Call this before ``db.add()`` / ``db.flush()`` so scope is present on the
    first INSERT.

    Usage::

        apply_tenant_scope(db_sale, current_user, app_mode=settings.APP_MODE)
    """
    if not is_pos_mode(app_mode):
        return

    if current_user.organization_id is not None:
        obj.organization_id = current_user.organization_id

    if current_user.branch_id is not None:
        obj.branch_id = current_user.branch_id


def require_operational_tenant_scope(
    current_user: "User",
    *,
    app_mode: str | None,
    deployment_profile: str | None = None,
) -> None:
    """Reject hosted operational writes from incompletely provisioned users."""
    if not is_pos_mode(app_mode) or not is_hosted_deployment(
        deployment_profile,
        app_mode=app_mode,
    ):
        return

    if current_user.organization_id is None or current_user.branch_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hosted POS user must be assigned to an organization and branch",
        )


def scope_query_to_user(
    query,
    model: Any,
    current_user: "User",
    *,
    app_mode: str | None,
    include_branch: bool = True,
    deployment_profile: str | None = None,
):
    """Apply organization and optional branch ownership to an ORM query."""
    organization_id = getattr(current_user, "organization_id", None)
    branch_id = getattr(current_user, "branch_id", None)

    if organization_id is None:
        if is_pos_mode(app_mode) and is_hosted_deployment(
            deployment_profile,
            app_mode=app_mode,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Hosted POS user must be assigned to an organization",
            )
        return query

    if hasattr(model, "organization_id"):
        query = query.filter(model.organization_id == organization_id)
    if include_branch and branch_id is not None and hasattr(model, "branch_id"):
        query = query.filter(model.branch_id == branch_id)
    return query
