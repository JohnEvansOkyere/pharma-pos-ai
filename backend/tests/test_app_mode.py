from app.core.app_mode import (
    apply_tenant_scope,
    is_cloud_reporting_mode,
    is_local_operational_write,
    is_online_pos_mode,
    is_pos_mode,
    normalize_app_mode,
    require_online_tenant_scope,
)
from fastapi import HTTPException
import pytest


def test_normalize_app_mode_defaults_to_local_pos_for_invalid_value():
    assert normalize_app_mode(None) == "local_pos"
    assert normalize_app_mode("unexpected") == "local_pos"
    assert normalize_app_mode(" CLOUD_REPORTING ") == "cloud_reporting"


def test_normalize_app_mode_accepts_online_pos():
    assert normalize_app_mode("online_pos") == "online_pos"
    assert normalize_app_mode(" ONLINE_POS ") == "online_pos"


def test_is_online_pos_mode():
    assert is_online_pos_mode("online_pos") is True
    assert is_online_pos_mode("local_pos") is False
    assert is_online_pos_mode("cloud_reporting") is False
    assert is_online_pos_mode(None) is False


def test_is_pos_mode():
    assert is_pos_mode("local_pos") is True
    assert is_pos_mode("online_pos") is True
    assert is_pos_mode("cloud_reporting") is False
    assert is_pos_mode(None) is True  # defaults to local_pos


def test_cloud_reporting_blocks_local_operational_writes():
    blocked_requests = [
        ("POST", "/api/sales"),
        ("POST", "/api/sales/1/refund"),
        ("POST", "/api/products/1/receive-stock"),
        ("PUT", "/api/suppliers/1"),
        ("DELETE", "/api/notifications/1"),
        ("POST", "/api/system/backup-now"),
    ]

    for method, path in blocked_requests:
        assert is_local_operational_write(
            app_mode="cloud_reporting",
            method=method,
            path=path,
        )


def test_cloud_reporting_allows_reporting_and_cloud_admin_requests():
    allowed_requests = [
        ("GET", "/api/products"),
        ("POST", "/api/auth/login"),
        ("POST", "/api/sync/ingest"),
        ("POST", "/api/sync/project"),
        ("POST", "/api/ai-manager/chat"),
        ("POST", "/api/cloud-reports/reconciliation/acknowledge"),
        ("POST", "/api/admin/organizations"),
    ]

    for method, path in allowed_requests:
        assert not is_local_operational_write(
            app_mode="cloud_reporting",
            method=method,
            path=path,
        )


def test_local_pos_mode_does_not_block_operational_writes():
    assert not is_local_operational_write(
        app_mode="local_pos",
        method="POST",
        path="/api/sales",
    )


def test_online_pos_mode_does_not_block_operational_writes():
    """online_pos mode allows all POS writes just like local_pos."""
    assert not is_local_operational_write(
        app_mode="online_pos",
        method="POST",
        path="/api/sales",
    )
    assert not is_local_operational_write(
        app_mode="online_pos",
        method="POST",
        path="/api/products",
    )
    assert not is_local_operational_write(
        app_mode="online_pos",
        method="POST",
        path="/api/system/backup-now",
    )


def test_online_pos_write_requires_organization_and_branch():
    class User:
        organization_id = None
        branch_id = None

    with pytest.raises(HTTPException) as exc:
        require_online_tenant_scope(User(), app_mode="online_pos")

    assert exc.value.status_code == 403


def test_online_pos_scope_is_applied_before_insert():
    class User:
        organization_id = 12
        branch_id = 34

    class Row:
        organization_id = None
        branch_id = None

    row = Row()
    require_online_tenant_scope(User(), app_mode="online_pos")
    apply_tenant_scope(row, User(), app_mode="online_pos")

    assert row.organization_id == 12
    assert row.branch_id == 34
