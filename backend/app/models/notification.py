"""
Notification model for system alerts.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
from enum import Enum

from app.db.base import Base


class NotificationType(str, Enum):
    """Notification type enumeration."""
    EXPIRY = "expiry"
    LOW_STOCK = "low_stock"
    DEAD_STOCK = "dead_stock"
    SYSTEM = "system"


class NotificationPriority(str, Enum):
    """Notification priority enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Notification(Base):
    """Notification model for alerts and warnings."""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(SQLEnum(NotificationType), nullable=False, index=True)
    priority = Column(SQLEnum(NotificationPriority), default=NotificationPriority.MEDIUM, nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    related_entity_id = Column(Integer)  # Product ID, Batch ID, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<Notification(id={self.id}, type='{self.type}', priority='{self.priority}')>"
