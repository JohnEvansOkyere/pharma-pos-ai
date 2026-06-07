"""Stable identity helpers for events crossing operational database boundaries."""
from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid5


GLOBAL_ID_NAMESPACE = UUID("66cc8c97-b21e-4a6a-b5c8-09fa3a52ca45")


def canonical_uuid(value: str) -> str:
    return str(UUID(str(value)))


def legacy_organization_uid(organization_id: int) -> str:
    return str(uuid5(GLOBAL_ID_NAMESPACE, f"organization:{organization_id}"))


def legacy_branch_uid(organization_id: int, branch_id: int) -> str:
    return str(
        uuid5(
            GLOBAL_ID_NAMESPACE,
            f"organization:{organization_id}:branch:{branch_id}",
        )
    )


def legacy_deployment_uid(device_uid: str) -> str:
    return str(uuid5(GLOBAL_ID_NAMESPACE, f"device:{device_uid}:deployment"))


def build_aggregate_uid(
    deployment_uid: str,
    aggregate_type: str,
    aggregate_id: Optional[int],
) -> Optional[str]:
    if aggregate_id is None:
        return None
    namespace = UUID(canonical_uuid(deployment_uid))
    return str(uuid5(namespace, f"{aggregate_type}:{aggregate_id}"))
