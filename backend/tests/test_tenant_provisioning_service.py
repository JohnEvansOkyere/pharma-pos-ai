from __future__ import annotations

import json
import stat

import pytest

from app.models import Branch, Device, Organization
from app.models.user import User, UserRole
from app.services.tenant_provisioning_service import (
    TenantIdentity,
    TenantSecrets,
    build_render_postgres_payload,
    build_render_service_payload,
    load_or_create_state,
    register_control_plane,
    run_migrations,
    seed_tenant_database,
)


def _identity() -> TenantIdentity:
    return TenantIdentity.create(
        organization_name="Provisioned Pharmacy",
        branch_name="Main Branch",
        branch_code="MAIN",
        device_name="Hosted Backend",
    )


def _secrets() -> TenantSecrets:
    return TenantSecrets(
        secret_key="s" * 64,
        sync_token="sync-token-value",
        admin_password="Admin-Password-123",
    )


def test_load_or_create_state_is_private_and_resumable(tmp_path):
    state, identity, tenant_secrets = load_or_create_state(
        tmp_path,
        organization_name="Provisioned Pharmacy",
        branch_name="Main Branch",
        branch_code="MAIN",
        device_name="Hosted Backend",
        admin_username="tenant-owner",
        admin_email="owner@example.com",
        admin_full_name="Tenant Owner",
    )
    resumed_state, resumed_identity, resumed_secrets = load_or_create_state(
        tmp_path,
        organization_name="Provisioned Pharmacy",
        branch_name="Main Branch",
        branch_code="MAIN",
        device_name="Hosted Backend",
        admin_username="tenant-owner",
        admin_email="owner@example.com",
        admin_full_name="Tenant Owner",
    )

    assert state == resumed_state
    assert identity == resumed_identity
    assert tenant_secrets == resumed_secrets
    assert stat.S_IMODE((tmp_path / "state.json").stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "secrets.json").stat().st_mode) == 0o600
    assert "sync_token" not in json.loads(
        (tmp_path / "state.json").read_text()
    )


def test_seed_tenant_database_is_idempotent_and_scopes_admin(db_session):
    identity = _identity()
    tenant_secrets = _secrets()

    first = seed_tenant_database(
        db_session,
        identity=identity,
        tenant_secrets=tenant_secrets,
        admin_username="tenant-owner",
        admin_email="owner@example.com",
        admin_full_name="Tenant Owner",
    )
    second = seed_tenant_database(
        db_session,
        identity=identity,
        tenant_secrets=tenant_secrets,
        admin_username="tenant-owner",
        admin_email="owner@example.com",
        admin_full_name="Tenant Owner",
    )

    organization = db_session.query(Organization).filter(
        Organization.organization_uid == identity.organization_uid
    ).one()
    branch = db_session.query(Branch).filter(
        Branch.branch_uid == identity.branch_uid
    ).one()
    device = db_session.query(Device).filter(
        Device.device_uid == identity.device_uid
    ).one()
    admin = db_session.query(User).filter(User.username == "tenant-owner").one()

    assert first == second
    assert branch.organization_id == organization.id
    assert device.organization_id == organization.id
    assert device.branch_id == branch.id
    assert device.deployment_uid == identity.deployment_uid
    assert admin.role == UserRole.ADMIN
    assert admin.organization_id == organization.id
    assert admin.branch_id is None


def test_register_control_plane_hashes_token_and_is_idempotent(db_session):
    identity = _identity()
    tenant_secrets = _secrets()

    first = register_control_plane(
        db_session,
        identity=identity,
        tenant_secrets=tenant_secrets,
    )
    second = register_control_plane(
        db_session,
        identity=identity,
        tenant_secrets=tenant_secrets,
    )

    device = db_session.query(Device).filter(
        Device.device_uid == identity.device_uid
    ).one()
    assert first == second
    assert device.token_hash
    assert device.token_hash != tenant_secrets.sync_token


def test_render_postgres_payload_rejects_free_plan():
    with pytest.raises(ValueError, match="free plan"):
        build_render_postgres_payload(
            slug="provisioned-pharmacy",
            owner_id="tea-owner",
            region="frankfurt",
            plan="free",
            disk_size_gb=5,
            provisioner_cidr="203.0.113.8/32",
        )


def test_render_postgres_payload_limits_external_access_to_provisioner():
    payload = build_render_postgres_payload(
        slug="provisioned-pharmacy",
        owner_id="tea-owner",
        region="frankfurt",
        plan="basic_256mb",
        disk_size_gb=5,
        provisioner_cidr="203.0.113.8/32",
    )

    assert payload["ipAllowList"] == [
        {
            "cidrBlock": "203.0.113.8/32",
            "description": "Temporary vendor provisioning access",
        }
    ]


def test_render_postgres_payload_rejects_broad_provisioner_network():
    with pytest.raises(ValueError, match="exactly one IP"):
        build_render_postgres_payload(
            slug="provisioned-pharmacy",
            owner_id="tea-owner",
            region="frankfurt",
            plan="basic_256mb",
            disk_size_gb=5,
            provisioner_cidr="203.0.113.0/24",
        )


def test_run_migrations_uses_explicit_database_url(tmp_path):
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))

    run_migrations(
        "postgresql://tenant.example/pharma",
        backend_dir=tmp_path,
        runner=runner,
    )

    command, kwargs = calls[0]
    assert command[-4:] == ["-m", "alembic", "upgrade", "head"]
    assert kwargs["cwd"] == tmp_path
    assert kwargs["env"]["DATABASE_URL"] == "postgresql://tenant.example/pharma"
    assert kwargs["check"] is True


def test_render_service_payload_uses_isolated_runtime_and_global_ids():
    identity = _identity()
    payload = build_render_service_payload(
        slug="provisioned-pharmacy",
        owner_id="tea-owner",
        region="frankfurt",
        plan="starter",
        repo="https://github.com/example/pharma-pos-ai.git",
        branch="main",
        database_url="postgresql://tenant-internal",
        central_ingest_url="https://central.example/api/sync/ingest",
        cors_origins="https://tenant.example",
        identity=identity,
        tenant_secrets=_secrets(),
        control_plane_ids={"organization_id": 10, "branch_id": 20},
    )
    environment = {
        item["key"]: item["value"]
        for item in payload["envVars"]
    }

    assert payload["type"] == "web_service"
    assert payload["serviceDetails"]["preDeployCommand"] == (
        "python -m alembic upgrade head"
    )
    assert environment["APP_MODE"] == "operational_pos"
    assert environment["POS_DEPLOYMENT_PROFILE"] == "hosted"
    assert environment["DATABASE_URL"] == "postgresql://tenant-internal"
    assert environment["CLOUD_SYNC_ORGANIZATION_UID"] == (
        identity.organization_uid
    )
    assert environment["CLOUD_SYNC_BRANCH_UID"] == identity.branch_uid
    assert environment["CLOUD_SYNC_DEPLOYMENT_UID"] == identity.deployment_uid
