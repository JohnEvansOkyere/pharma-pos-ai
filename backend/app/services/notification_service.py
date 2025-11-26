"""
Notification service for creating and managing system notifications.
"""
from typing import Optional
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
import httpx
import logging

from app.models.notification import Notification, NotificationType, NotificationPriority
from app.models.product import Product, ProductBatch
from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing notifications."""

    @staticmethod
    def create_notification(
        db: Session,
        type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        related_entity_id: Optional[int] = None
    ) -> Notification:
        """
        Create a new notification.

        Args:
            db: Database session
            type: Notification type
            title: Notification title
            message: Notification message
            priority: Notification priority
            related_entity_id: Related entity ID (product, batch, etc.)

        Returns:
            Created notification
        """
        notification = Notification(
            type=type,
            priority=priority,
            title=title,
            message=message,
            related_entity_id=related_entity_id,
        )

        db.add(notification)
        db.commit()
        db.refresh(notification)

        # Send webhook if enabled
        if settings.ENABLE_EMAIL_NOTIFICATIONS and settings.N8N_WEBHOOK_URL:
            NotificationService.send_webhook(notification)

        return notification

    @staticmethod
    def send_webhook(notification: Notification):
        """
        Send notification to external webhook (e.g., n8n for email).

        Args:
            notification: Notification object
        """
        if not settings.N8N_WEBHOOK_URL:
            return

        try:
            payload = {
                "type": notification.type.value,
                "priority": notification.priority.value,
                "title": notification.title,
                "message": notification.message,
                "created_at": notification.created_at.isoformat(),
            }

            with httpx.Client() as client:
                response = client.post(
                    settings.N8N_WEBHOOK_URL,
                    json=payload,
                    timeout=5.0
                )
                response.raise_for_status()
                logger.info(f"Webhook sent successfully for notification {notification.id}")

        except Exception as e:
            logger.error(f"Failed to send webhook: {str(e)}")

    @staticmethod
    def check_expiring_products(db: Session):
        """
        Check for products nearing expiry and create notifications.

        Args:
            db: Database session
        """
        expiry_threshold = date.today() + timedelta(days=settings.EXPIRY_WARNING_DAYS)

        expiring_batches = db.query(ProductBatch).filter(
            ProductBatch.expiry_date <= expiry_threshold,
            ProductBatch.expiry_date >= date.today(),
            ProductBatch.quantity > 0
        ).all()

        for batch in expiring_batches:
            # Check if notification already exists for this batch
            existing = db.query(Notification).filter(
                Notification.type == NotificationType.EXPIRY,
                Notification.related_entity_id == batch.id,
                Notification.created_at >= datetime.now() - timedelta(days=1)
            ).first()

            if not existing:
                days_until_expiry = (batch.expiry_date - date.today()).days
                product = batch.product

                priority = NotificationPriority.CRITICAL if days_until_expiry <= 7 else NotificationPriority.HIGH

                NotificationService.create_notification(
                    db=db,
                    type=NotificationType.EXPIRY,
                    title=f"Product Expiring Soon: {product.name}",
                    message=f"Batch {batch.batch_number} expires in {days_until_expiry} days. "
                           f"Quantity: {batch.quantity}",
                    priority=priority,
                    related_entity_id=batch.id
                )

        logger.info(f"Checked expiring products. Found {len(expiring_batches)} batches.")

    @staticmethod
    def check_low_stock(db: Session):
        """
        Check for low stock products and create notifications.

        Args:
            db: Database session
        """
        low_stock_products = db.query(Product).filter(
            Product.total_stock <= Product.low_stock_threshold,
            Product.is_active == True
        ).all()

        for product in low_stock_products:
            # Check if notification already exists for this product
            existing = db.query(Notification).filter(
                Notification.type == NotificationType.LOW_STOCK,
                Notification.related_entity_id == product.id,
                Notification.created_at >= datetime.now() - timedelta(days=1)
            ).first()

            if not existing:
                priority = NotificationPriority.CRITICAL if product.total_stock == 0 else NotificationPriority.HIGH

                NotificationService.create_notification(
                    db=db,
                    type=NotificationType.LOW_STOCK,
                    title=f"Low Stock Alert: {product.name}",
                    message=f"Current stock: {product.total_stock}. "
                           f"Threshold: {product.low_stock_threshold}",
                    priority=priority,
                    related_entity_id=product.id
                )

        logger.info(f"Checked low stock. Found {len(low_stock_products)} products.")
