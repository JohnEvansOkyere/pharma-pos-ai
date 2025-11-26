"""
Pydantic schemas for Notification model.
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from app.models.notification import NotificationType, NotificationPriority


class NotificationBase(BaseModel):
    """Base notification schema."""
    type: NotificationType
    priority: NotificationPriority = NotificationPriority.MEDIUM
    title: str = Field(..., max_length=200)
    message: str
    related_entity_id: Optional[int] = None


class NotificationCreate(NotificationBase):
    """Schema for creating a notification."""
    pass


class Notification(NotificationBase):
    """Schema for notification response."""
    id: int
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationUpdate(BaseModel):
    """Schema for updating a notification."""
    is_read: bool
