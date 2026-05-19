from app.core.app_mode import is_local_operational_write, normalize_app_mode


def test_normalize_app_mode_defaults_to_local_pos_for_invalid_value():
    assert normalize_app_mode(None) == "local_pos"
    assert normalize_app_mode("unexpected") == "local_pos"
    assert normalize_app_mode(" CLOUD_REPORTING ") == "cloud_reporting"


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
