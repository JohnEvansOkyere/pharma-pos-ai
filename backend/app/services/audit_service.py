"""
Audit logging helpers for critical system mutations.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog


class AuditService:
    """Helpers for recording server-side audit events."""

    HASH_VERSION = 1
    GENESIS_HASH = "0" * 64
    ADVISORY_LOCK_NAMESPACE = 910_300_000

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {key: AuditService._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [AuditService._json_safe(item) for item in value]
        return value

    @staticmethod
    def _iso_datetime(value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    @staticmethod
    def _scope_key(organization_id: Optional[int]) -> int:
        return organization_id or 0

    @staticmethod
    def _lock_scope(db: Session, organization_id: Optional[int]) -> None:
        bind = db.get_bind()
        if bind.dialect.name != "postgresql":
            return
        lock_key = AuditService.ADVISORY_LOCK_NAMESPACE + AuditService._scope_key(organization_id)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})

    @staticmethod
    def _latest_hash(db: Session, organization_id: Optional[int]) -> str:
        query = db.query(ActivityLog).filter(ActivityLog.current_hash.is_not(None))
        if organization_id is None:
            query = query.filter(ActivityLog.organization_id.is_(None))
        else:
            query = query.filter(ActivityLog.organization_id == organization_id)
        latest = query.order_by(ActivityLog.id.desc()).with_for_update().first()
        return latest.current_hash if latest and latest.current_hash else AuditService.GENESIS_HASH

    @staticmethod
    def canonical_payload(entry: ActivityLog) -> dict[str, Any]:
        """Return the deterministic payload used to hash one audit row."""
        return {
            "hash_version": entry.hash_version,
            "id": entry.id,
            "organization_id": entry.organization_id,
            "branch_id": entry.branch_id,
            "source_device_id": entry.source_device_id,
            "user_id": entry.user_id,
            "action": entry.action,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "description": entry.description,
            "extra_data": AuditService._json_safe(entry.extra_data),
            "ip_address": entry.ip_address,
            "created_at": AuditService._iso_datetime(entry.created_at),
            "previous_hash": entry.previous_hash,
        }

    @staticmethod
    def hash_entry(entry: ActivityLog) -> str:
        canonical = json.dumps(
            AuditService.canonical_payload(entry),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def log(
        db: Session,
        *,
        action: str,
        user_id: Optional[int],
        entity_type: str,
        entity_id: Optional[int],
        description: str,
        extra_data: Optional[dict[str, Any]] = None,
        organization_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        source_device_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> ActivityLog:
        AuditService._lock_scope(db, organization_id)
        previous_hash = AuditService._latest_hash(db, organization_id)
        entry = ActivityLog(
            organization_id=organization_id,
            branch_id=branch_id,
            source_device_id=source_device_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            extra_data=AuditService._json_safe(extra_data),
            ip_address=ip_address,
            hash_version=AuditService.HASH_VERSION,
            previous_hash=previous_hash,
            created_at=datetime.now(timezone.utc),
        )
        db.add(entry)
        db.flush()
        entry.current_hash = AuditService.hash_entry(entry)
        db.flush()
        return entry

    @staticmethod
    def verify_integrity(
        db: Session,
        *,
        organization_id: Optional[int] = None,
    ) -> dict[str, Any]:
        query = db.query(ActivityLog)
        if organization_id is None:
            scope_label = "all"
        else:
            scope_label = str(organization_id)
            query = query.filter(ActivityLog.organization_id == organization_id)

        rows = query.order_by(ActivityLog.organization_id.asc().nullsfirst(), ActivityLog.id.asc()).all()
        expected_hash_by_scope: dict[Optional[int], str] = {}
        chain_started_by_scope: set[Optional[int]] = set()
        sealed_count = 0
        unsealed_count = 0
        unsealed_after_chain_count = 0
        invalid_count = 0
        issues: list[dict[str, Any]] = []
        latest_log_id: Optional[int] = None
        latest_hash: Optional[str] = None

        for entry in rows:
            latest_log_id = entry.id
            scope_key = entry.organization_id
            has_chain_fields = bool(entry.hash_version and entry.previous_hash and entry.current_hash)

            if not has_chain_fields:
                unsealed_count += 1
                if scope_key in chain_started_by_scope:
                    unsealed_after_chain_count += 1
                    invalid_count += 1
                    if len(issues) < 20:
                        issues.append(
                            {
                                "log_id": entry.id,
                                "organization_id": entry.organization_id,
                                "issue_type": "unsealed_after_chain_started",
                                "message": "Audit row has no hash fields after the organization chain started.",
                            }
                        )
                continue

            chain_started_by_scope.add(scope_key)
            sealed_count += 1
            expected_previous_hash = expected_hash_by_scope.get(scope_key, AuditService.GENESIS_HASH)
            if entry.hash_version != AuditService.HASH_VERSION:
                invalid_count += 1
                if len(issues) < 20:
                    issues.append(
                        {
                            "log_id": entry.id,
                            "organization_id": entry.organization_id,
                            "issue_type": "unsupported_hash_version",
                            "message": f"Unsupported audit hash version {entry.hash_version}.",
                        }
                    )
            if entry.previous_hash != expected_previous_hash:
                invalid_count += 1
                if len(issues) < 20:
                    issues.append(
                        {
                            "log_id": entry.id,
                            "organization_id": entry.organization_id,
                            "issue_type": "broken_previous_hash",
                            "message": "Audit row previous_hash does not match the prior sealed row.",
                        }
                    )

            expected_current_hash = AuditService.hash_entry(entry)
            if entry.current_hash != expected_current_hash:
                invalid_count += 1
                if len(issues) < 20:
                    issues.append(
                        {
                            "log_id": entry.id,
                            "organization_id": entry.organization_id,
                            "issue_type": "current_hash_mismatch",
                            "message": "Audit row current_hash does not match its canonical payload.",
                        }
                    )

            expected_hash_by_scope[scope_key] = entry.current_hash or expected_current_hash
            latest_hash = entry.current_hash

        return {
            "scope": scope_label,
            "organization_id": organization_id,
            "checked_at": datetime.now(timezone.utc),
            "valid": invalid_count == 0 and unsealed_after_chain_count == 0,
            "total_count": len(rows),
            "sealed_count": sealed_count,
            "unsealed_count": unsealed_count,
            "unsealed_after_chain_count": unsealed_after_chain_count,
            "invalid_count": invalid_count,
            "first_invalid_log_id": issues[0]["log_id"] if issues else None,
            "latest_log_id": latest_log_id,
            "latest_hash": latest_hash,
            "issues": issues,
        }
