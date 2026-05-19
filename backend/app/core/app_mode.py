"""
Application mode helpers.

The same codebase can run as a local pharmacy POS or as the deployed cloud
reporting portal. Cloud reporting mode must not behave like a second till.
"""

from __future__ import annotations

from typing import Iterable


LOCAL_POS_MODE = "local_pos"
CLOUD_REPORTING_MODE = "cloud_reporting"
VALID_APP_MODES = {LOCAL_POS_MODE, CLOUD_REPORTING_MODE}

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
