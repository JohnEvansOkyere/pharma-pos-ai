from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.api.endpoints import system_ops
from app.api.endpoints.system_ops import get_restore_drill_status, record_restore_drill
from app.core.security import get_password_hash
from app.models.activity_log import ActivityLog
from app.models.user import User, UserRole
from app.schemas.system import BackupStatus, RestoreDrillCreate


def _admin(db_session):
    user = User(
        username="restore-admin",
        email="restore-admin@example.com",
        hashed_password=get_password_hash("admin-secret"),
        full_name="Restore Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _backup_status(*, exists=True, recent=True):
    return BackupStatus(
        platform="Linux",
        backup_dir="/var/backups/pharma",
        latest_backup_path="/var/backups/pharma/latest.dump" if exists else None,
        latest_backup_exists=exists,
        latest_backup_time=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat() if exists else None,
        latest_backup_size_bytes=2048 if exists else None,
        latest_backup_age_hours=1.0 if exists else None,
        backup_is_recent=recent,
        retention_days=30,
        trigger_available=True,
        schedule_helper_available=True,
    )


def test_admin_records_successful_restore_drill_and_status(db_session, monkeypatch):
    admin = _admin(db_session)
    monkeypatch.setattr(system_ops, "_build_backup_status", lambda: _backup_status())

    result = record_restore_drill(
        RestoreDrillCreate(
            status="passed",
            restore_target="Technician laptop restore database",
            notes="Verified users, latest sale, and product stock counts.",
            verification_summary={"users_checked": True, "stock_checked": True},
        ),
        db=db_session,
        current_user=admin,
    )
    status = get_restore_drill_status(db=db_session, current_user=admin)
    audit_entry = (
        db_session.query(ActivityLog)
        .filter(ActivityLog.action == "record_restore_drill")
        .order_by(ActivityLog.id.desc())
        .first()
    )

    assert result.status == "passed"
    assert result.backup_path == "/var/backups/pharma/latest.dump"
    assert status.recovery_ready is True
    assert status.latest_backup_tested is True
    assert status.last_drill is not None
    assert status.last_drill.restore_target == "Technician laptop restore database"
    assert audit_entry is not None
    assert audit_entry.current_hash is not None


def test_restore_drill_status_requires_recent_success(db_session, monkeypatch):
    admin = _admin(db_session)
    monkeypatch.setattr(system_ops, "_build_backup_status", lambda: _backup_status())

    result = get_restore_drill_status(db=db_session, current_user=admin)

    assert result.recovery_ready is False
    assert result.last_drill is None
    assert {item.key: item.status for item in result.checklist}["restore_drill_recent"] == "failed"


def test_restore_drill_record_requires_backup_path(db_session, monkeypatch):
    admin = _admin(db_session)
    monkeypatch.setattr(system_ops, "_build_backup_status", lambda: _backup_status(exists=False, recent=False))

    with pytest.raises(HTTPException) as exc:
        record_restore_drill(
            RestoreDrillCreate(
                status="passed",
                restore_target="Staging restore database",
            ),
            db=db_session,
            current_user=admin,
        )

    assert exc.value.status_code == 400
    assert "backup path" in exc.value.detail.lower()


def test_restore_drill_rejects_unknown_status(db_session, monkeypatch):
    admin = _admin(db_session)
    monkeypatch.setattr(system_ops, "_build_backup_status", lambda: _backup_status())

    with pytest.raises(HTTPException) as exc:
        record_restore_drill(
            RestoreDrillCreate(
                status="maybe",
                restore_target="Staging restore database",
            ),
            db=db_session,
            current_user=admin,
        )

    assert exc.value.status_code == 422
