"""
Audit logging helpers for critical system mutations.
"""
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog


class AuditService:
    """Helpers for recording server-side audit events."""

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, dict):
            return {key: AuditService._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [AuditService._json_safe(item) for item in value]
        return value

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
        ip_address: Optional[str] = None,
    ) -> ActivityLog:
        entry = ActivityLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            extra_data=AuditService._json_safe(extra_data),
            ip_address=ip_address,
        )
        db.add(entry)
        return entry
