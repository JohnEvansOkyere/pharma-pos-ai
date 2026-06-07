from fastapi import HTTPException
import pytest
from unittest.mock import MagicMock

from app.core.app_mode import (
    apply_tenant_scope,
    is_cloud_reporting_mode,
    is_hosted_deployment,
    is_local_operational_write,
    is_pos_mode,
    normalize_app_mode,
    require_operational_tenant_scope,
    scope_query_to_user,
)
from app.core.config import Settings


def test_normalize_app_mode_uses_one_operational_mode():
    assert normalize_app_mode(None) == "operational_pos"
    assert normalize_app_mode("unexpected") == "operational_pos"
    assert normalize_app_mode(" OPERATIONAL_POS ") == "operational_pos"
    assert normalize_app_mode("local_pos") == "operational_pos"
    assert normalize_app_mode("online_pos") == "operational_pos"
    assert normalize_app_mode(" CLOUD_REPORTING ") == "cloud_reporting"


def test_deployment_profile_is_independent_from_app_mode():
    assert is_hosted_deployment("hosted", app_mode="operational_pos") is True
    assert is_hosted_deployment("offline", app_mode="operational_pos") is False
    assert is_hosted_deployment(app_mode="online_pos") is True


def test_legacy_settings_aliases_derive_deployment_profile():
    common = {
        "_env_file": None,
        "ENVIRONMENT": "development",
        "SECRET_KEY": "x" * 32,
        "POSTGRES_PASSWORD": "test-password",
    }

    local = Settings.model_validate({"APP_MODE": "local_pos", **common})
    hosted = Settings.model_validate({"APP_MODE": "online_pos", **common})

    assert local.APP_MODE == "operational_pos"
    assert local.POS_DEPLOYMENT_PROFILE == "offline"
    assert local.CUSTOMER_RETENTION_ENABLED is False
    assert hosted.APP_MODE == "operational_pos"
    assert hosted.POS_DEPLOYMENT_PROFILE == "hosted"
    assert hosted.CUSTOMER_RETENTION_ENABLED is True


def test_is_pos_mode():
    assert is_pos_mode("operational_pos") is True
    assert is_pos_mode("local_pos") is True
    assert is_pos_mode("online_pos") is True
    assert is_pos_mode("cloud_reporting") is False
    assert is_pos_mode(None) is True


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


def test_operational_mode_does_not_block_writes():
    assert not is_local_operational_write(
        app_mode="operational_pos",
        method="POST",
        path="/api/sales",
    )


def test_hosted_write_requires_organization_and_branch():
    class User:
        organization_id = None
        branch_id = None

    with pytest.raises(HTTPException) as exc:
        require_operational_tenant_scope(
            User(),
            app_mode="operational_pos",
            deployment_profile="hosted",
        )

    assert exc.value.status_code == 403


def test_offline_write_allows_legacy_unscoped_install():
    class User:
        organization_id = None
        branch_id = None

    require_operational_tenant_scope(
        User(),
        app_mode="operational_pos",
        deployment_profile="offline",
    )


def test_operational_scope_is_applied_before_insert():
    class User:
        organization_id = 12
        branch_id = 34

    class Row:
        organization_id = None
        branch_id = None

    row = Row()
    require_operational_tenant_scope(
        User(),
        app_mode="operational_pos",
        deployment_profile="hosted",
    )
    apply_tenant_scope(row, User(), app_mode="operational_pos")

    assert row.organization_id == 12
    assert row.branch_id == 34


def test_offline_query_scope_preserves_dedicated_database_visibility():
    class User:
        organization_id = 12
        branch_id = 34

    class Model:
        organization_id = 1
        branch_id = 2

    query = MagicMock()
    scoped = scope_query_to_user(
        query,
        Model,
        User(),
        app_mode="operational_pos",
        deployment_profile="offline",
    )

    assert scoped is query
    query.filter.assert_not_called()


def test_hosted_query_scope_filters_organization_and_branch():
    class User:
        organization_id = 12
        branch_id = 34

    class Model:
        organization_id = 1
        branch_id = 2

    query = MagicMock()
    query.filter.return_value = query
    scoped = scope_query_to_user(
        query,
        Model,
        User(),
        app_mode="operational_pos",
        deployment_profile="hosted",
    )

    assert scoped is query
    assert query.filter.call_count == 2


def test_cloud_reporting_query_scope_keeps_existing_tenant_filtering():
    class User:
        organization_id = 12
        branch_id = 34

    class Model:
        organization_id = 1
        branch_id = 2

    query = MagicMock()
    query.filter.return_value = query
    scoped = scope_query_to_user(
        query,
        Model,
        User(),
        app_mode="cloud_reporting",
        deployment_profile="hosted",
    )

    assert scoped is query
    assert query.filter.call_count == 2


def test_cloud_reporting_mode_helper():
    assert is_cloud_reporting_mode("cloud_reporting") is True
    assert is_cloud_reporting_mode("operational_pos") is False
