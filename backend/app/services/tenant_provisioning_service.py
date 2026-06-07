"""Repeatable provisioning helpers for isolated pharmacy deployments."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import hashlib
from ipaddress import ip_network
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
from typing import Any, Callable, Optional
from uuid import uuid4

import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import get_password_hash
from app.models.tenancy import Branch, Device, DeviceStatus, Organization
from app.models.user import User, UserRole
from app.services.sync_identity_service import canonical_uuid


STATE_VERSION = 1
RENDER_API_BASE_URL = "https://api.render.com/v1"
ALLOWED_TENANT_RUNTIME_ENV = {
    "SMS_PROVIDER",
    "SMS_SENDER_ID",
    "SMS_API_KEY",
    "SMS_USERNAME",
    "SMS_FROM_NUMBER",
    "SMS_CLIENT_ID",
    "SMS_CLIENT_SECRET",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GROQ_API_KEY",
    "AI_MANAGER_PROVIDER",
    "AI_MANAGER_MODEL",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_FROM_EMAIL",
    "SMTP_FROM_NAME",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_WEBHOOK_SECRET",
}
SENSITIVE_TENANT_RUNTIME_ENV = {
    "SMS_API_KEY",
    "SMS_CLIENT_ID",
    "SMS_CLIENT_SECRET",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GROQ_API_KEY",
    "SMTP_PASSWORD",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_WEBHOOK_SECRET",
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise ValueError("Organization name must contain at least one letter or number")
    return slug[:40]


@dataclass(frozen=True)
class TenantIdentity:
    organization_name: str
    branch_name: str
    branch_code: str
    device_name: str
    organization_uid: str
    branch_uid: str
    deployment_uid: str
    device_uid: str

    @classmethod
    def create(
        cls,
        *,
        organization_name: str,
        branch_name: str,
        branch_code: str,
        device_name: str,
    ) -> "TenantIdentity":
        return cls(
            organization_name=organization_name,
            branch_name=branch_name,
            branch_code=branch_code,
            device_name=device_name,
            organization_uid=str(uuid4()),
            branch_uid=str(uuid4()),
            deployment_uid=str(uuid4()),
            device_uid=str(uuid4()),
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TenantIdentity":
        identity = cls(**value)
        for field_name in (
            "organization_uid",
            "branch_uid",
            "deployment_uid",
            "device_uid",
        ):
            canonical_uuid(getattr(identity, field_name))
        return identity


@dataclass(frozen=True)
class TenantSecrets:
    secret_key: str
    sync_token: str
    admin_password: str
    runtime_env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(cls) -> "TenantSecrets":
        return cls(
            secret_key=secrets.token_urlsafe(64),
            sync_token=secrets.token_urlsafe(48),
            admin_password=secrets.token_urlsafe(24),
            runtime_env={},
        )


def write_json_private(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.chmod(path, 0o600)


def write_secrets_private(path: Path, tenant_secrets: TenantSecrets) -> None:
    write_json_private(path, asdict(tenant_secrets))


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_tenant_runtime_env(path: Path) -> dict[str, str]:
    if hasattr(os, "geteuid") and path.stat().st_uid != os.geteuid():
        raise RuntimeError(f"Tenant secrets file is not owned by the current user: {path}")
    mode = stat_mode(path)
    if mode & 0o077:
        raise RuntimeError(
            f"Tenant secrets file must not be accessible by group or others: {path}"
        )
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError("Tenant secrets file must contain one JSON object")
    return {
        str(key): str(item).strip()
        for key, item in value.items()
        if item is not None and str(item).strip()
    }


def stat_mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


def validate_tenant_runtime_env(
    runtime_env: dict[str, str],
    *,
    require_sms_credentials: bool,
) -> dict[str, str]:
    unknown = set(runtime_env) - ALLOWED_TENANT_RUNTIME_ENV
    if unknown:
        raise ValueError(
            "Unsupported tenant runtime secret keys: "
            + ", ".join(sorted(unknown))
        )

    validated = dict(runtime_env)
    provider = validated.get("SMS_PROVIDER", "stub").lower()
    if provider not in {"stub", "africas_talking", "hubtel"}:
        raise ValueError("SMS_PROVIDER must be stub, africas_talking, or hubtel")
    validated["SMS_PROVIDER"] = provider

    required_by_provider = {
        "africas_talking": {"SMS_API_KEY", "SMS_USERNAME", "SMS_SENDER_ID"},
        "hubtel": {
            "SMS_CLIENT_ID",
            "SMS_CLIENT_SECRET",
            "SMS_FROM_NUMBER",
            "SMS_SENDER_ID",
        },
    }
    if require_sms_credentials and provider == "stub":
        raise ValueError(
            "Hosted tenant provisioning requires a real tenant-specific SMS provider"
        )
    missing = required_by_provider.get(provider, set()) - set(validated)
    if missing:
        raise ValueError(
            f"{provider} tenant credentials are missing: "
            + ", ".join(sorted(missing))
        )
    return validated


def secret_fingerprints(tenant_secrets: TenantSecrets) -> dict[str, str]:
    values = {
        "SECRET_KEY": tenant_secrets.secret_key,
        "CLOUD_SYNC_API_TOKEN": tenant_secrets.sync_token,
        **{
            key: value
            for key, value in tenant_secrets.runtime_env.items()
            if key in SENSITIVE_TENANT_RUNTIME_ENV
        },
    }
    return {
        key: hashlib.sha256(value.encode()).hexdigest()
        for key, value in sorted(values.items())
    }


def _assert_secret_fingerprints_unique(
    state_root: Path,
    *,
    current_state_dir: Path,
    fingerprints: dict[str, str],
) -> None:
    for state_path in state_root.glob("*/state.json"):
        if state_path.parent == current_state_dir:
            continue
        other = read_json(state_path).get("secret_fingerprints", {})
        for key, fingerprint in fingerprints.items():
            if fingerprint in other.values():
                raise RuntimeError(
                    f"{key} is already assigned to another tenant state"
                )


def configure_tenant_runtime_secrets(
    state_dir: Path,
    state: dict[str, Any],
    tenant_secrets: TenantSecrets,
    runtime_env: dict[str, str],
    *,
    require_sms_credentials: bool,
) -> TenantSecrets:
    validated = validate_tenant_runtime_env(
        runtime_env,
        require_sms_credentials=require_sms_credentials,
    )
    if tenant_secrets.runtime_env and tenant_secrets.runtime_env != validated:
        raise RuntimeError(
            "Tenant runtime secrets differ from the recorded bundle; use an "
            "audited rotation workflow instead of overwriting provisioning state"
        )
    updated = replace(tenant_secrets, runtime_env=validated)
    fingerprints = secret_fingerprints(updated)
    _assert_secret_fingerprints_unique(
        state_dir.parent,
        current_state_dir=state_dir,
        fingerprints=fingerprints,
    )
    state["secret_fingerprints"] = fingerprints
    write_secrets_private(state_dir / "secrets.json", updated)
    save_state(state_dir, state)
    return updated


def load_or_create_state(
    state_dir: Path,
    *,
    organization_name: str,
    branch_name: str,
    branch_code: str,
    device_name: str,
    admin_username: str,
    admin_email: str,
    admin_full_name: str,
) -> tuple[dict[str, Any], TenantIdentity, TenantSecrets]:
    state_path = state_dir / "state.json"
    secrets_path = state_dir / "secrets.json"
    if state_path.exists() != secrets_path.exists():
        raise RuntimeError(
            f"Provisioning state is incomplete in {state_dir}; preserve it and investigate"
        )

    if state_path.exists():
        state = read_json(state_path)
        if state.get("version") != STATE_VERSION:
            raise RuntimeError(
                f"Unsupported provisioning state version in {state_path}"
            )
        stored_secrets = read_json(secrets_path)
        tenant_secrets = TenantSecrets(
            secret_key=stored_secrets["secret_key"],
            sync_token=stored_secrets["sync_token"],
            admin_password=stored_secrets["admin_password"],
            runtime_env=stored_secrets.get("runtime_env", {}),
        )
        identity = TenantIdentity.from_dict(state["identity"])
        requested = (
            organization_name,
            branch_name,
            branch_code,
            device_name,
        )
        recorded = (
            identity.organization_name,
            identity.branch_name,
            identity.branch_code,
            identity.device_name,
        )
        if requested != recorded:
            raise RuntimeError(
                "Requested tenant details do not match the existing provisioning state"
            )
        requested_admin = {
            "username": admin_username,
            "email": admin_email.lower(),
            "full_name": admin_full_name,
        }
        if requested_admin != state.get("admin"):
            raise RuntimeError(
                "Requested admin details do not match the existing provisioning state"
            )
        return state, identity, tenant_secrets

    identity = TenantIdentity.create(
        organization_name=organization_name,
        branch_name=branch_name,
        branch_code=branch_code,
        device_name=device_name,
    )
    tenant_secrets = TenantSecrets.create()
    state = {
        "version": STATE_VERSION,
        "slug": slugify(organization_name),
        "identity": asdict(identity),
        "admin": {
            "username": admin_username,
            "email": admin_email.lower(),
            "full_name": admin_full_name,
        },
        "render": {},
        "steps": {},
    }
    write_json_private(state_path, state)
    write_secrets_private(secrets_path, tenant_secrets)
    return state, identity, tenant_secrets


def save_state(state_dir: Path, state: dict[str, Any]) -> None:
    write_json_private(state_dir / "state.json", state)


def _assert_existing_identity(
    actual: str,
    expected: str,
    *,
    resource_name: str,
) -> None:
    if canonical_uuid(actual) != canonical_uuid(expected):
        raise RuntimeError(
            f"{resource_name} already exists with a different control-plane identity"
        )


def seed_tenant_database(
    db: Session,
    *,
    identity: TenantIdentity,
    tenant_secrets: TenantSecrets,
    admin_username: str,
    admin_email: str,
    admin_full_name: str,
) -> dict[str, int]:
    organization = (
        db.query(Organization)
        .filter(Organization.organization_uid == identity.organization_uid)
        .first()
    )
    if organization is None:
        organization = db.query(Organization).filter(
            Organization.name == identity.organization_name
        ).first()
    if organization is None:
        organization = Organization(
            organization_uid=identity.organization_uid,
            name=identity.organization_name,
            is_active=True,
        )
        db.add(organization)
        db.flush()
    else:
        _assert_existing_identity(
            organization.organization_uid,
            identity.organization_uid,
            resource_name="Tenant organization",
        )

    branch = (
        db.query(Branch)
        .filter(Branch.branch_uid == identity.branch_uid)
        .first()
    )
    if branch is None:
        branch = (
            db.query(Branch)
            .filter(
                Branch.organization_id == organization.id,
                Branch.code == identity.branch_code,
            )
            .first()
        )
    if branch is None:
        branch = Branch(
            branch_uid=identity.branch_uid,
            organization_id=organization.id,
            name=identity.branch_name,
            code=identity.branch_code,
            is_active=True,
        )
        db.add(branch)
        db.flush()
    else:
        _assert_existing_identity(
            branch.branch_uid,
            identity.branch_uid,
            resource_name="Tenant branch",
        )
        if branch.organization_id != organization.id:
            raise RuntimeError("Tenant branch belongs to a different organization")

    device = db.query(Device).filter(Device.device_uid == identity.device_uid).first()
    if device is None:
        device = Device(
            organization_id=organization.id,
            branch_id=branch.id,
            device_uid=identity.device_uid,
            deployment_uid=identity.deployment_uid,
            name=identity.device_name,
            status=DeviceStatus.ACTIVE,
        )
        db.add(device)
        db.flush()
    else:
        _assert_existing_identity(
            device.deployment_uid,
            identity.deployment_uid,
            resource_name="Tenant deployment",
        )
        if (
            device.organization_id != organization.id
            or device.branch_id != branch.id
        ):
            raise RuntimeError("Tenant device belongs to a different tenant scope")

    admin = db.query(User).filter(
        User.organization_id == organization.id,
        User.username == admin_username,
    ).first()
    if admin is None:
        admin = User(
            username=admin_username,
            email=admin_email.lower(),
            full_name=admin_full_name,
            hashed_password=get_password_hash(tenant_secrets.admin_password),
            role=UserRole.ADMIN,
            organization_id=organization.id,
            branch_id=None,
            is_active=True,
        )
        db.add(admin)
        db.flush()
    else:
        if admin.role != UserRole.ADMIN:
            raise RuntimeError("Existing tenant owner username is not an admin")
        admin.email = admin_email.lower()
        admin.full_name = admin_full_name
        admin.hashed_password = get_password_hash(tenant_secrets.admin_password)
        admin.branch_id = None
        admin.is_active = True

    db.commit()
    return {
        "organization_id": organization.id,
        "branch_id": branch.id,
        "device_id": device.id,
        "admin_user_id": admin.id,
    }


def register_control_plane(
    db: Session,
    *,
    identity: TenantIdentity,
    tenant_secrets: TenantSecrets,
) -> dict[str, int]:
    organization = (
        db.query(Organization)
        .filter(Organization.organization_uid == identity.organization_uid)
        .first()
    )
    if organization is None:
        organization = Organization(
            organization_uid=identity.organization_uid,
            name=identity.organization_name,
            is_active=True,
        )
        db.add(organization)
        db.flush()
    elif organization.name != identity.organization_name:
        raise RuntimeError("Control-plane organization UUID belongs to another tenant")

    branch = (
        db.query(Branch)
        .filter(Branch.branch_uid == identity.branch_uid)
        .first()
    )
    if branch is None:
        branch = (
            db.query(Branch)
            .filter(
                Branch.organization_id == organization.id,
                Branch.code == identity.branch_code,
            )
            .first()
        )
    if branch is None:
        branch = Branch(
            branch_uid=identity.branch_uid,
            organization_id=organization.id,
            name=identity.branch_name,
            code=identity.branch_code,
            is_active=True,
        )
        db.add(branch)
        db.flush()
    else:
        _assert_existing_identity(
            branch.branch_uid,
            identity.branch_uid,
            resource_name="Control-plane branch",
        )
        if branch.organization_id != organization.id:
            raise RuntimeError("Control-plane branch belongs to another organization")

    token_hash = hashlib.sha256(tenant_secrets.sync_token.encode()).hexdigest()
    device = db.query(Device).filter(Device.device_uid == identity.device_uid).first()
    if device is None:
        device = Device(
            organization_id=organization.id,
            branch_id=branch.id,
            device_uid=identity.device_uid,
            deployment_uid=identity.deployment_uid,
            name=identity.device_name,
            token_hash=token_hash,
            status=DeviceStatus.ACTIVE,
        )
        db.add(device)
        db.flush()
    else:
        _assert_existing_identity(
            device.deployment_uid,
            identity.deployment_uid,
            resource_name="Control-plane deployment",
        )
        if (
            device.organization_id != organization.id
            or device.branch_id != branch.id
        ):
            raise RuntimeError("Control-plane device belongs to another tenant scope")
        device.token_hash = token_hash
        device.status = DeviceStatus.ACTIVE

    db.commit()
    return {
        "organization_id": organization.id,
        "branch_id": branch.id,
        "device_id": device.id,
    }


def session_factory(database_url: str) -> sessionmaker:
    engine = create_engine(database_url, pool_pre_ping=True)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def run_migrations(
    database_url: str,
    *,
    backend_dir: Path,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "DATABASE_BACKEND": "postgresql",
            "DATABASE_URL": database_url,
            "ENVIRONMENT": "development",
            "SECRET_KEY": environment.get("SECRET_KEY") or secrets.token_urlsafe(32),
        }
    )
    runner(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        check=True,
    )


class RenderAPIClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = RENDER_API_BASE_URL,
        timeout_seconds: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def _request(self, method: str, path: str, **kwargs) -> Any:
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            timeout=self.timeout_seconds,
            **kwargs,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Render API {method} {path} failed with "
                f"{response.status_code}: {response.text[:500]}"
            )
        return response.json() if response.content else None

    def create_postgres(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/postgres", json=payload)

    def get_postgres(self, postgres_id: str) -> dict[str, Any]:
        return self._request("GET", f"/postgres/{postgres_id}")

    def get_postgres_connection_info(self, postgres_id: str) -> dict[str, Any]:
        return self._request("GET", f"/postgres/{postgres_id}/connection-info")

    def update_postgres(
        self,
        postgres_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self._request("PATCH", f"/postgres/{postgres_id}", json=payload)

    def create_service(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/services", json=payload)

    def wait_for_postgres(
        self,
        postgres_id: str,
        *,
        timeout_seconds: int = 900,
        poll_seconds: int = 10,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            postgres = self.get_postgres(postgres_id)
            status = postgres.get("status")
            if status == "available":
                return postgres
            if status in {"unavailable", "recovery_failed", "suspended"}:
                raise RuntimeError(
                    f"Render Postgres {postgres_id} entered status {status}"
                )
            time.sleep(poll_seconds)
        raise TimeoutError(f"Timed out waiting for Render Postgres {postgres_id}")


def build_render_postgres_payload(
    *,
    slug: str,
    owner_id: str,
    region: str,
    plan: str,
    disk_size_gb: int,
    provisioner_cidr: str,
    environment_id: Optional[str] = None,
) -> dict[str, Any]:
    if plan == "free":
        raise ValueError("Production tenant databases cannot use Render's free plan")
    network = ip_network(provisioner_cidr, strict=False)
    if network.prefixlen != network.max_prefixlen:
        raise ValueError(
            "Render provisioner CIDR must identify exactly one IP address"
        )
    payload: dict[str, Any] = {
        "name": f"pharma-{slug}-db",
        "databaseName": f"pharma_{slug.replace('-', '_')}"[:63],
        "databaseUser": f"pharma_{slug.replace('-', '_')}"[:63],
        "ownerId": owner_id,
        "plan": plan,
        "region": region,
        "version": "15",
        "diskSizeGB": disk_size_gb,
        "enableDiskAutoscaling": True,
        "enableHighAvailability": False,
        "ipAllowList": [
            {
                "cidrBlock": str(network),
                "description": "Temporary vendor provisioning access",
            }
        ],
    }
    if environment_id:
        payload["environmentId"] = environment_id
    return payload


def build_render_service_payload(
    *,
    slug: str,
    owner_id: str,
    region: str,
    plan: str,
    repo: str,
    branch: str,
    database_url: str,
    central_ingest_url: str,
    cors_origins: str,
    identity: TenantIdentity,
    tenant_secrets: TenantSecrets,
    control_plane_ids: dict[str, int],
    environment_id: Optional[str] = None,
) -> dict[str, Any]:
    environment = {
        "DATABASE_BACKEND": "postgresql",
        "DATABASE_URL": database_url,
        "SECRET_KEY": tenant_secrets.secret_key,
        "ENVIRONMENT": "production",
        "APP_MODE": "operational_pos",
        "POS_DEPLOYMENT_PROFILE": "hosted",
        "DEBUG": "false",
        "TIMEZONE": "Africa/Accra",
        "BACKEND_CORS_ORIGINS": cors_origins,
        "ENABLE_BACKGROUND_SCHEDULER": "true",
        "CUSTOMER_RETENTION_ENABLED": "true",
        "CUSTOMER_RECEIPTS_ENABLED": "true",
        "CUSTOMER_FOLLOWUPS_ENABLED": "true",
        "CLOUD_SYNC_ENABLED": "true",
        "CLOUD_SYNC_INGEST_URL": central_ingest_url,
        "CLOUD_SYNC_API_TOKEN": tenant_secrets.sync_token,
        "CLOUD_SYNC_DEVICE_UID": identity.device_uid,
        "CLOUD_SYNC_DEPLOYMENT_UID": identity.deployment_uid,
        "CLOUD_SYNC_ORGANIZATION_ID": str(
            control_plane_ids["organization_id"]
        ),
        "CLOUD_SYNC_BRANCH_ID": str(control_plane_ids["branch_id"]),
        "CLOUD_SYNC_ORGANIZATION_UID": identity.organization_uid,
        "CLOUD_SYNC_BRANCH_UID": identity.branch_uid,
        "CLOUD_PROJECTION_ENABLED": "false",
    }
    environment.update(tenant_secrets.runtime_env)
    payload: dict[str, Any] = {
        "type": "web_service",
        "name": f"pharma-{slug}-backend",
        "ownerId": owner_id,
        "repo": repo,
        "branch": branch,
        "autoDeploy": "yes",
        "rootDir": "backend",
        "envVars": [
            {"key": key, "value": value}
            for key, value in sorted(environment.items())
        ],
        "serviceDetails": {
            "runtime": "python",
            "plan": plan,
            "region": region,
            "healthCheckPath": "/health",
            "preDeployCommand": "python -m alembic upgrade head",
            "envSpecificDetails": {
                "buildCommand": (
                    "pip install --upgrade pip && pip install -r requirements.txt"
                ),
                "startCommand": (
                    "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
                ),
            },
        },
    }
    if environment_id:
        payload["environmentId"] = environment_id
    return payload
