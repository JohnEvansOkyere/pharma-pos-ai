"""
Restore drill records for backup recovery readiness.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class RestoreDrill(Base):
    """Technician-recorded proof that a backup was restored and checked."""

    __tablename__ = "restore_drills"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(20), nullable=False, index=True)
    backup_path = Column(Text, nullable=False)
    backup_created_at = Column(DateTime(timezone=True), nullable=True)
    backup_size_bytes = Column(Integer, nullable=True)
    restore_target = Column(String(300), nullable=False)
    notes = Column(Text, nullable=True)
    verification_summary = Column(JSON, nullable=False, default=dict)
    tested_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tested_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
