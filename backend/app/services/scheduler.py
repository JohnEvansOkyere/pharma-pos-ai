"""
Background scheduler for periodic tasks.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.services.ai_report_delivery_service import AIReportDeliveryService
from app.services.ai_weekly_report_service import AIWeeklyReportService
from app.services.cloud_projection_service import CloudProjectionService
from app.services.full_snapshot_sync_service import FullSnapshotSyncService
from app.services.notification_service import NotificationService
from app.services.system_heartbeat_service import SystemHeartbeatService
from app.services.sync_upload_service import SyncUploadService
from app.core.config import settings

logger = logging.getLogger(__name__)


class SchedulerService:
    """Background scheduler service."""

    def __init__(self):
        # Configure scheduler with explicit timezone
        tz = timezone(getattr(settings, 'TIMEZONE', 'UTC'))
        self.scheduler = BackgroundScheduler(timezone=tz)

    def start(self):
        """Start the background scheduler."""
        if not settings.ENABLE_BACKGROUND_SCHEDULER:
            logger.info("Background scheduler disabled in settings")
            return

        # Get timezone for cron jobs
        tz = timezone(getattr(settings, 'TIMEZONE', 'UTC'))
        
        # Schedule expiry checks
        self.scheduler.add_job(
            self.check_expiring_products,
            CronTrigger(hour=settings.EXPIRY_CHECK_HOUR, minute=0, timezone=tz),
            id="check_expiring_products",
            name="Check expiring products",
            replace_existing=True,
        )

        # Schedule low stock checks
        self.scheduler.add_job(
            self.check_low_stock,
            CronTrigger(hour=settings.LOW_STOCK_CHECK_HOUR, minute=0, timezone=tz),
            id="check_low_stock",
            name="Check low stock",
            replace_existing=True,
        )

        # Schedule near expiry checks (critical - check twice daily)
        self.scheduler.add_job(
            self.check_near_expiry,
            CronTrigger(hour="8,20", minute=0, timezone=tz),
            id="check_near_expiry",
            name="Check near expiry products",
            replace_existing=True,
        )

        # Schedule dead stock checks (weekly - Monday at 11 AM)
        self.scheduler.add_job(
            self.check_dead_stock,
            CronTrigger(day_of_week="mon", hour=11, minute=0, timezone=tz),
            id="check_dead_stock",
            name="Check dead stock",
            replace_existing=True,
        )

        # Schedule overstock checks (weekly - Monday at 11:30 AM)
        self.scheduler.add_job(
            self.check_overstock,
            CronTrigger(day_of_week="mon", hour=11, minute=30, timezone=tz),
            id="check_overstock",
            name="Check overstock",
            replace_existing=True,
        )

        # Sync outbox jobs are only meaningful for local_pos installations.
        # In online_pos mode, POS writes go directly to the cloud DB — no
        # outbox upload, heartbeat, or catalog snapshot sync is needed.
        from app.core.app_mode import is_online_pos_mode
        if settings.CLOUD_SYNC_ENABLED and not is_online_pos_mode(settings.APP_MODE):
            self.scheduler.add_job(
                self.enqueue_system_heartbeat,
                "interval",
                minutes=settings.CLOUD_HEARTBEAT_INTERVAL_MINUTES,
                id="enqueue_system_heartbeat",
                name="Enqueue system heartbeat",
                replace_existing=True,
            )
            self.scheduler.add_job(
                self.upload_sync_events,
                "interval",
                minutes=settings.CLOUD_SYNC_INTERVAL_MINUTES,
                id="upload_sync_events",
                name="Upload sync events",
                replace_existing=True,
            )
            if settings.CLOUD_CATALOG_SNAPSHOT_SYNC_ENABLED:
                self.scheduler.add_job(
                    self.nightly_cloud_catalog_sync,
                    CronTrigger(
                        hour=settings.CLOUD_CATALOG_SNAPSHOT_SYNC_HOUR,
                        minute=settings.CLOUD_CATALOG_SNAPSHOT_SYNC_MINUTE,
                        timezone=tz,
                    ),
                    id="nightly_cloud_catalog_sync",
                    name="Nightly cloud catalog sync",
                    replace_existing=True,
                )

        # Cloud projection is only meaningful for cloud_reporting deployments
        # that ingest sync events from local installs. In online_pos mode the
        # data is already in the main database tables.
        if settings.CLOUD_PROJECTION_ENABLED and not is_online_pos_mode(settings.APP_MODE):
            self.scheduler.add_job(
                self.project_cloud_events,
                "interval",
                minutes=settings.CLOUD_PROJECTION_INTERVAL_MINUTES,
                id="project_cloud_events",
                name="Project cloud sync events",
                replace_existing=True,
            )

        if settings.AI_WEEKLY_REPORTS_ENABLED:
            self.scheduler.add_job(
                self.generate_weekly_ai_reports,
                CronTrigger(
                    day_of_week=settings.AI_WEEKLY_REPORT_DAY,
                    hour=settings.AI_WEEKLY_REPORT_HOUR,
                    minute=settings.AI_WEEKLY_REPORT_MINUTE,
                    timezone=tz,
                ),
                id="generate_weekly_ai_reports",
                name="Generate weekly AI manager reports",
                replace_existing=True,
            )

        if settings.TELEGRAM_ALERTS_ENABLED and settings.TELEGRAM_BOT_TOKEN:
            self.scheduler.add_job(
                self.push_telegram_alerts,
                "interval",
                minutes=settings.TELEGRAM_ALERT_INTERVAL_MINUTES,
                id="push_telegram_alerts",
                name="Push Telegram anomaly alerts",
                replace_existing=True,
            )

        if settings.AI_DAILY_BRIEFING_ENABLED:
            self.scheduler.add_job(
                self.send_daily_briefing,
                CronTrigger(hour=settings.AI_DAILY_BRIEFING_HOUR, minute=0, timezone=tz),
                id="send_daily_briefing",
                name="Send daily AI briefing via Telegram",
                replace_existing=True,
            )

        if settings.AI_WEEKLY_REPORT_DELIVERY_RETRY_ENABLED:
            self.scheduler.add_job(
                self.retry_weekly_ai_report_deliveries,
                "interval",
                minutes=settings.AI_WEEKLY_REPORT_DELIVERY_RETRY_INTERVAL_MINUTES,
                id="retry_weekly_ai_report_deliveries",
                name="Retry failed weekly AI report deliveries",
                replace_existing=True,
            )

        # Customer follow-up dispatch — only meaningful in online_pos mode
        # where the retention module is active and customers are registered.
        if is_online_pos_mode(settings.APP_MODE):
            self.scheduler.add_job(
                self.dispatch_customer_follow_ups,
                "interval",
                hours=1,
                id="dispatch_customer_follow_ups",
                name="Dispatch customer follow-up messages",
                replace_existing=True,
            )

        self.scheduler.start()
        logger.info(f"Background scheduler started with timezone: {tz}")
        
        # Log next run times for debugging
        for job in self.scheduler.get_jobs():
            logger.info(f"Job '{job.name}' - Next run: {job.next_run_time}")

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
            logger.exception("Error in expiry check task")
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
            logger.exception("Error in low stock check task")
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
            logger.exception("Error in out of stock check task")
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
            logger.exception("Error in near expiry check task")
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
            logger.exception("Error in dead stock check task")
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
            logger.exception("Error in overstock check task")
        finally:
            db.close()

    @staticmethod
    def upload_sync_events():
        """Task to upload pending local sync events to the cloud ingestion API."""
        db: Session = SessionLocal()
        try:
            logger.info("Running cloud sync upload task")
            result = SyncUploadService.upload_pending(db)
            logger.info("Cloud sync upload result: %s", result)
        except Exception as e:
            logger.exception("Error in cloud sync upload task")
        finally:
            db.close()

    @staticmethod
    def nightly_cloud_catalog_sync():
        """Queue a full local catalog snapshot and upload it after closing time."""
        db: Session = SessionLocal()
        try:
            logger.info("Running nightly cloud catalog sync task")
            snapshot = FullSnapshotSyncService.enqueue_catalog_snapshot(db)
            db.commit()
            upload = SyncUploadService.upload_pending(db)
            logger.info("Nightly cloud catalog sync snapshot=%s upload=%s", snapshot, upload)
            if upload.get("failed", 0) > 0:
                logger.error("Nightly cloud catalog sync failed for %s event(s); run manual local backup and retry", upload["failed"])
        except Exception:
            db.rollback()
            logger.exception("Error in nightly cloud catalog sync task; run manual local backup and retry")
        finally:
            db.close()

    @staticmethod
    def enqueue_system_heartbeat():
        """Task to record local installation telemetry into the sync outbox."""
        db: Session = SessionLocal()
        try:
            logger.info("Running system heartbeat enqueue task")
            event = SystemHeartbeatService.enqueue_heartbeat(
                db,
                scheduler_running=bool(scheduler.scheduler.running),
                scheduler_job_count=len(scheduler.scheduler.get_jobs()),
            )
            db.commit()
            logger.info("System heartbeat queued as sync event %s", event.event_id)
        except Exception as e:
            db.rollback()
            logger.exception("Error in system heartbeat task")
        finally:
            db.close()

    @staticmethod
    def project_cloud_events():
        """Task to project accepted cloud sync events into reporting tables."""
        db: Session = SessionLocal()
        try:
            logger.info("Running cloud projection task")
            result = CloudProjectionService.project_pending(
                db,
                limit=settings.CLOUD_PROJECTION_BATCH_SIZE,
            )
            logger.info("Cloud projection result: %s", result)
        except Exception as e:
            logger.exception("Error in cloud projection task")
        finally:
            db.close()

    @staticmethod
    def generate_weekly_ai_reports():
        """Task to generate saved weekly manager reports for active organizations."""
        db: Session = SessionLocal()
        try:
            logger.info("Running weekly AI manager report generation task")
            reports = AIWeeklyReportService.generate_all(
                db,
                deliver=settings.AI_WEEKLY_REPORT_DELIVERY_ENABLED,
            )
            logger.info("Generated %s weekly AI manager report(s)", len(reports))
        except Exception as e:
            logger.exception("Error in weekly AI manager report task")
        finally:
            db.close()

    @staticmethod
    def push_telegram_alerts():
        """Task to detect business anomalies and push Telegram alerts to the CEO."""
        db: Session = SessionLocal()
        try:
            logger.info("Running Telegram anomaly alert task")
            from app.services.telegram_alert_service import TelegramAlertService
            count = TelegramAlertService.push_alerts_all_orgs(db)
            logger.info("Pushed %s Telegram alert(s)", count)
        except Exception:
            logger.exception("Error in Telegram alert push task")
        finally:
            db.close()

    @staticmethod
    def send_daily_briefing():
        """Task to send the daily morning briefing to all orgs with Telegram configured."""
        db: Session = SessionLocal()
        try:
            logger.info("Running daily AI briefing task")
            from app.services.telegram_alert_service import TelegramAlertService
            count = TelegramAlertService.send_daily_briefing_all_orgs(db)
            logger.info("Sent %s daily briefing(s)", count)
        except Exception:
            logger.exception("Error in daily AI briefing task")
        finally:
            db.close()

    @staticmethod
    def retry_weekly_ai_report_deliveries():
        """Task to retry transient failed weekly report deliveries."""
        db: Session = SessionLocal()
        try:
            logger.info("Running weekly AI report delivery retry task")
            deliveries = AIReportDeliveryService.retry_due(db)
            logger.info("Retried %s weekly AI report delivery record(s)", len(deliveries))
        except Exception as e:
            logger.exception("Error in weekly AI report delivery retry task")
        finally:
            db.close()

    @staticmethod
    def dispatch_customer_follow_ups():
        """Hourly task: send all due customer health follow-up messages.

        Only runs in online_pos mode (registered via is_online_pos_mode guard
        in start()). Uses the message adapter (stub by default) — plug in a
        real SMS provider via SMS_PROVIDER env var.
        """
        db: Session = SessionLocal()
        try:
            from app.services.customer_retention_service import process_pending_follow_ups
            from app.core.config import settings as _settings
            pharmacy_name = getattr(_settings, "APP_NAME", "PharmaPOS")
            result = process_pending_follow_ups(db, pharmacy_name=pharmacy_name)
            logger.info(
                "Follow-up dispatch: sent=%s skipped=%s failed=%s total=%s",
                result["sent"], result["skipped"], result["failed"], result["total_processed"],
            )
        except Exception:
            logger.exception("Error in customer follow-up dispatch task")
        finally:
            db.close()


# Global scheduler instance
scheduler = SchedulerService()
