"""
Activity log model for audit trail.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class ActivityLog(Base):
    """Activity log for tracking user actions and system events."""

    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(100), nullable=False, index=True)  # e.g., "create_product", "update_sale"
    entity_type = Column(String(50))  # e.g., "product", "sale", "user"
    entity_id = Column(Integer)
    description = Column(Text)
    metadata = Column(JSON)  # Additional contextual data
    ip_address = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="activity_logs")

    def __repr__(self):
        return f"<ActivityLog(id={self.id}, action='{self.action}', user_id={self.user_id})>"
