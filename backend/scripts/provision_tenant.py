#!/usr/bin/env python3
"""Provision one isolated pharmacy database and its control-plane registration."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parent.parent
REPOSITORY_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

# Importing application models initializes settings. Provisioning uses explicit
# database URLs, so these defaults only keep that import independent of runtime
# production secrets.
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SECRET_KEY", "provisioning-tool-only-secret-key-0001")

from app.services.tenant_provisioning_service import (  # noqa: E402
    RenderAPIClient,
    build_render_postgres_payload,
    build_render_service_payload,
    configure_tenant_runtime_secrets,
    load_or_create_state,
    load_tenant_runtime_env,
    register_control_plane,
    run_migrations,
    save_state,
    seed_tenant_database,
    session_factory,
    slugify,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Provision one isolated pharmacy tenant. The command is a dry run "
            "unless --apply is supplied."
        )
    )
    parser.add_argument("--organization-name", required=True)
    parser.add_argument("--branch-name", default="Main Branch")
    parser.add_argument("--branch-code", default="MAIN")
    parser.add_argument("--device-name", default="Hosted Backend")
    parser.add_argument("--admin-username", required=True)
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-full-name", required=True)
    parser.add_argument(
        "--control-plane-database-url",
        default=os.getenv("CONTROL_PLANE_DATABASE_URL"),
    )
    parser.add_argument(
        "--central-ingest-url",
        default=os.getenv(
            "CENTRAL_INGEST_URL",
            "https://pharma-pos-ai.onrender.com/api/sync/ingest",
        ),
    )
    parser.add_argument(
        "--tenant-database-url",
        default=os.getenv("TENANT_DATABASE_URL"),
    )
    parser.add_argument(
        "--tenant-secrets-file",
        type=Path,
        default=Path(os.environ["TENANT_SECRETS_FILE"])
        if os.getenv("TENANT_SECRETS_FILE")
        else None,
        help="Owner-only JSON file containing tenant-specific messaging/API keys",
    )
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--render-api-key", default=os.getenv("RENDER_API_KEY"))
    parser.add_argument("--render-owner-id", default=os.getenv("RENDER_OWNER_ID"))
    parser.add_argument(
        "--render-environment-id",
        default=os.getenv("RENDER_ENVIRONMENT_ID"),
    )
    parser.add_argument("--render-region", default=os.getenv("RENDER_REGION"))
    parser.add_argument(
        "--render-postgres-plan",
        default=os.getenv("RENDER_POSTGRES_PLAN", "basic_256mb"),
    )
    parser.add_argument(
        "--render-postgres-disk-gb",
        type=int,
        default=int(os.getenv("RENDER_POSTGRES_DISK_GB", "5")),
    )
    parser.add_argument(
        "--render-provisioner-cidr",
        default=os.getenv("RENDER_PROVISIONER_CIDR"),
        help="Exact vendor public IP in CIDR form, for example 203.0.113.8/32",
    )
    parser.add_argument(
        "--render-service-plan",
        default=os.getenv("RENDER_SERVICE_PLAN", "starter"),
    )
    parser.add_argument(
        "--render-repo",
        default=os.getenv(
            "RENDER_REPO",
            "https://github.com/JohnEvansOkyere/pharma-pos-ai.git",
        ),
    )
    parser.add_argument(
        "--render-branch",
        default=os.getenv("RENDER_BRANCH", "main"),
    )
    parser.add_argument(
        "--cors-origins",
        default=os.getenv("TENANT_CORS_ORIGINS"),
    )
    parser.add_argument(
        "--state-root",
        type=Path,
        default=REPOSITORY_DIR / "var" / "provisioning",
    )
    parser.add_argument("--apply", action="store_true")
    return parser


def _require(value: str | None, name: str) -> str:
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def main() -> int:
    args = _parser().parse_args()
    if args.render and args.tenant_database_url:
        raise SystemExit("Use either --render or --tenant-database-url, not both")
    if not args.render and not args.tenant_database_url:
        raise SystemExit("Choose --render or provide --tenant-database-url")

    tenant_slug = slugify(args.organization_name)
    state_dir = args.state_root / tenant_slug
    state, identity, tenant_secrets = load_or_create_state(
        state_dir,
        organization_name=args.organization_name,
        branch_name=args.branch_name,
        branch_code=args.branch_code,
        device_name=args.device_name,
        admin_username=args.admin_username,
        admin_email=args.admin_email,
        admin_full_name=args.admin_full_name,
    )

    print(f"Tenant: {identity.organization_name}")
    print(f"State: {state_dir}")
    print(f"Organization UID: {identity.organization_uid}")
    print(f"Branch UID: {identity.branch_uid}")
    print(f"Deployment UID: {identity.deployment_uid}")
    print(f"Device UID: {identity.device_uid}")
    if args.tenant_secrets_file:
        tenant_secrets = configure_tenant_runtime_secrets(
            state_dir,
            state,
            tenant_secrets,
            load_tenant_runtime_env(args.tenant_secrets_file),
            require_sms_credentials=args.render,
        )
    if not args.apply:
        print("Dry run only. Re-run with --apply to create or modify resources.")
        return 0

    control_plane_url = _require(
        args.control_plane_database_url,
        "CONTROL_PLANE_DATABASE_URL or --control-plane-database-url",
    )
    if args.render and not tenant_secrets.runtime_env:
        raise SystemExit(
            "TENANT_SECRETS_FILE or --tenant-secrets-file is required for hosted tenants"
        )

    render_client = None
    tenant_database_url = args.tenant_database_url
    internal_database_url = tenant_database_url
    if args.render:
        render_client = RenderAPIClient(
            _require(args.render_api_key, "RENDER_API_KEY or --render-api-key")
        )
        owner_id = _require(
            args.render_owner_id,
            "RENDER_OWNER_ID or --render-owner-id",
        )
        region = _require(
            args.render_region,
            "RENDER_REGION or --render-region",
        )
        provisioner_cidr = _require(
            args.render_provisioner_cidr,
            "RENDER_PROVISIONER_CIDR or --render-provisioner-cidr",
        )
        cors_origins = _require(
            args.cors_origins,
            "TENANT_CORS_ORIGINS or --cors-origins",
        )
        postgres_id = state["render"].get("postgres_id")
        if not postgres_id:
            postgres = render_client.create_postgres(
                build_render_postgres_payload(
                    slug=tenant_slug,
                    owner_id=owner_id,
                    region=region,
                    plan=args.render_postgres_plan,
                    disk_size_gb=args.render_postgres_disk_gb,
                    provisioner_cidr=provisioner_cidr,
                    environment_id=args.render_environment_id,
                )
            )
            postgres_id = postgres["id"]
            state["render"]["postgres_id"] = postgres_id
            state["render"]["postgres_dashboard_url"] = postgres.get(
                "dashboardUrl"
            )
            save_state(state_dir, state)
        render_client.wait_for_postgres(postgres_id)
        connection_info = render_client.get_postgres_connection_info(postgres_id)
        tenant_database_url = connection_info["externalConnectionString"]
        internal_database_url = connection_info["internalConnectionString"]

    if state["steps"].get("migrations") != "complete":
        run_migrations(
            _require(tenant_database_url, "Tenant database URL"),
            backend_dir=BACKEND_DIR,
        )
        state["steps"]["migrations"] = "complete"
        save_state(state_dir, state)

    if state["steps"].get("tenant_seed") != "complete":
        TenantSession = session_factory(tenant_database_url)
        with TenantSession() as tenant_db:
            tenant_ids = seed_tenant_database(
                tenant_db,
                identity=identity,
                tenant_secrets=tenant_secrets,
                admin_username=args.admin_username,
                admin_email=args.admin_email,
                admin_full_name=args.admin_full_name,
            )
        state["tenant_ids"] = tenant_ids
        state["steps"]["tenant_seed"] = "complete"
        save_state(state_dir, state)

    if state["steps"].get("control_plane_registration") != "complete":
        ControlPlaneSession = session_factory(control_plane_url)
        with ControlPlaneSession() as control_plane_db:
            control_plane_ids = register_control_plane(
                control_plane_db,
                identity=identity,
                tenant_secrets=tenant_secrets,
            )
        state["control_plane_ids"] = control_plane_ids
        state["steps"]["control_plane_registration"] = "complete"
        save_state(state_dir, state)
    control_plane_ids = state["control_plane_ids"]

    if render_client is not None and not state["render"].get("service_id"):
        service_response = render_client.create_service(
            build_render_service_payload(
                slug=tenant_slug,
                owner_id=args.render_owner_id,
                region=args.render_region,
                plan=args.render_service_plan,
                repo=args.render_repo,
                branch=args.render_branch,
                database_url=internal_database_url,
                central_ingest_url=args.central_ingest_url,
                cors_origins=cors_origins,
                identity=identity,
                tenant_secrets=tenant_secrets,
                control_plane_ids=control_plane_ids,
                environment_id=args.render_environment_id,
            )
        )
        service = service_response["service"]
        state["render"]["service_id"] = service["id"]
        state["render"]["service_dashboard_url"] = service.get("dashboardUrl")
        state["render"]["service_url"] = (
            service.get("serviceDetails") or {}
        ).get("url")
        state["steps"]["render_service"] = "created"
        save_state(state_dir, state)

    if (
        render_client is not None
        and state["steps"].get("external_database_access") != "disabled"
    ):
        render_client.update_postgres(postgres_id, {"ipAllowList": []})
        state["steps"]["external_database_access"] = "disabled"
        save_state(state_dir, state)

    print("Provisioning complete.")
    print(f"Non-secret receipt: {state_dir / 'state.json'}")
    print(f"Private generated credentials: {state_dir / 'secrets.json'}")
    print("Protect the credentials file and deliver the admin password separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
