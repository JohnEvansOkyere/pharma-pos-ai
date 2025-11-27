"""
Background scheduler for periodic tasks.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.services.notification_service import NotificationService
from app.core.config import settings

logger = logging.getLogger(__name__)


class SchedulerService:
    """Background scheduler service."""

    def __init__(self):
        self.scheduler = BackgroundScheduler()

    def start(self):
        """Start the background scheduler."""
        if not settings.ENABLE_BACKGROUND_SCHEDULER:
            logger.info("Background scheduler disabled in settings")
            return

        # Schedule expiry checks
        self.scheduler.add_job(
            self.check_expiring_products,
            CronTrigger(hour=settings.EXPIRY_CHECK_HOUR, minute=0),
            id="check_expiring_products",
            name="Check expiring products",
            replace_existing=True,
        )

        # Schedule low stock checks
        self.scheduler.add_job(
            self.check_low_stock,
            CronTrigger(hour=settings.LOW_STOCK_CHECK_HOUR, minute=0),
            id="check_low_stock",
            name="Check low stock",
            replace_existing=True,
        )

        # Schedule out of stock checks
        self.scheduler.add_job(
            self.check_out_of_stock,
            CronTrigger(hour=settings.LOW_STOCK_CHECK_HOUR, minute=15),
            id="check_out_of_stock",
            name="Check out of stock",
            replace_existing=True,
        )

        # Schedule near expiry checks (critical - check twice daily)
        self.scheduler.add_job(
            self.check_near_expiry,
            CronTrigger(hour="8,20", minute=0),
            id="check_near_expiry",
            name="Check near expiry products",
            replace_existing=True,
        )

        # Schedule dead stock checks (weekly - Monday at 11 AM)
        self.scheduler.add_job(
            self.check_dead_stock,
            CronTrigger(day_of_week="mon", hour=11, minute=0),
            id="check_dead_stock",
            name="Check dead stock",
            replace_existing=True,
        )

        # Schedule overstock checks (weekly - Monday at 11:30 AM)
        self.scheduler.add_job(
            self.check_overstock,
            CronTrigger(day_of_week="mon", hour=11, minute=30),
            id="check_overstock",
            name="Check overstock",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("Background scheduler started")

    def stop(self):
        """Stop the background scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Background scheduler stopped")

    @staticmethod
    def check_expiring_products():
        """Task to check for expiring products."""
        db: Session = SessionLocal()
        try:
            logger.info("Running expiry check task")
            NotificationService.check_expiring_products(db)
        except Exception as e:
            logger.error(f"Error in expiry check task: {str(e)}")
        finally:
            db.close()

    @staticmethod
    def check_low_stock():
        """Task to check for low stock products."""
        db: Session = SessionLocal()
        try:
            logger.info("Running low stock check task")
            NotificationService.check_low_stock(db)
        except Exception as e:
            logger.error(f"Error in low stock check task: {str(e)}")
        finally:
            db.close()

    @staticmethod
    def check_out_of_stock():
        """Task to check for out of stock products."""
        db: Session = SessionLocal()
        try:
            logger.info("Running out of stock check task")
            NotificationService.check_out_of_stock(db)
        except Exception as e:
            logger.error(f"Error in out of stock check task: {str(e)}")
        finally:
            db.close()

    @staticmethod
    def check_near_expiry():
        """Task to check for products expiring within 7 days."""
        db: Session = SessionLocal()
        try:
            logger.info("Running near expiry check task")
            NotificationService.check_near_expiry(db)
        except Exception as e:
            logger.error(f"Error in near expiry check task: {str(e)}")
        finally:
            db.close()

    @staticmethod
    def check_dead_stock():
        """Task to check for dead stock products."""
        db: Session = SessionLocal()
        try:
            logger.info("Running dead stock check task")
            NotificationService.check_dead_stock(db)
        except Exception as e:
            logger.error(f"Error in dead stock check task: {str(e)}")
        finally:
            db.close()

    @staticmethod
    def check_overstock():
        """Task to check for overstocked products."""
        db: Session = SessionLocal()
        try:
            logger.info("Running overstock check task")
            NotificationService.check_overstock(db)
        except Exception as e:
            logger.error(f"Error in overstock check task: {str(e)}")
        finally:
            db.close()


# Global scheduler instance
scheduler = SchedulerService()
