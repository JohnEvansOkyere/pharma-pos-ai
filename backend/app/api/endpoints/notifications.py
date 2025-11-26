"""
Notification API endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.schemas.notification import (
    Notification as NotificationSchema,
    NotificationUpdate,
)
from app.api.dependencies import get_current_active_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=List[NotificationSchema])
def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    is_read: Optional[bool] = None,
    type: Optional[NotificationType] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List notifications with filtering.

    Args:
        skip: Number of records to skip
        limit: Maximum records to return
        is_read: Filter by read status
        type: Filter by notification type
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of notifications
    """
    query = db.query(Notification)

    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)

    if type:
        query = query.filter(Notification.type == type)

    notifications = query.order_by(
        Notification.created_at.desc()
    ).offset(skip).limit(limit).all()

    return notifications


@router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Get count of unread notifications.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        Dictionary with unread count
    """
    count = db.query(Notification).filter(Notification.is_read == False).count()
    return {"unread_count": count}


@router.put("/{notification_id}", response_model=NotificationSchema)
def update_notification(
    notification_id: int,
    notification_update: NotificationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Mark notification as read/unread.

    Args:
        notification_id: Notification ID
        notification_update: Update data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated notification

    Raises:
        HTTPException: If notification not found
    """
    db_notification = db.query(Notification).filter(
        Notification.id == notification_id
    ).first()

    if not db_notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    db_notification.is_read = notification_update.is_read
    db.commit()
    db.refresh(db_notification)

    return db_notification


@router.put("/mark-all-read", status_code=status.HTTP_200_OK)
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Mark all notifications as read.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        Success message
    """
    db.query(Notification).filter(Notification.is_read == False).update(
        {"is_read": True}
    )
    db.commit()

    return {"message": "All notifications marked as read"}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a notification.

    Args:
        notification_id: Notification ID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: If notification not found
    """
    db_notification = db.query(Notification).filter(
        Notification.id == notification_id
    ).first()

    if not db_notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    db.delete(db_notification)
    db.commit()
