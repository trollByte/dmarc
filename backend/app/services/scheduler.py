"""
Background job scheduler for automated processing

This module handles scheduled tasks like:
- Processing pending DMARC reports
- Checking email for new reports (when ingestion is implemented)
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
from typing import Optional

from app.database import SessionLocal
from app.services.processing import ReportProcessor
from app.config import get_settings

logger = logging.getLogger(__name__)


class ReportScheduler:
    """Scheduler for automated DMARC report processing"""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.settings = get_settings()
        self._started = False

    def start(self):
        """Start the scheduler"""
        if self._started:
            logger.warning("Scheduler already started")
            return

        # Schedule report processing every 5 minutes
        self.scheduler.add_job(
            func=self._process_reports_job,
            trigger=IntervalTrigger(minutes=5),
            id='process_reports',
            name='Process pending DMARC reports',
            replace_existing=True
        )

        # Schedule email ingestion every 15 minutes (if email is configured)
        if self._is_email_configured():
            self.scheduler.add_job(
                func=self._ingest_emails_job,
                trigger=IntervalTrigger(minutes=15),
                id='ingest_emails',
                name='Check email for new DMARC reports',
                replace_existing=True
            )
            logger.info("Email ingestion job scheduled (every 15 minutes)")
        else:
            logger.info("Email ingestion job not scheduled (email not configured)")

        self.scheduler.start()
        self._started = True
        logger.info("Report scheduler started")
        logger.info("Scheduled jobs: %s", [job.id for job in self.scheduler.get_jobs()])

    def stop(self):
        """Stop the scheduler"""
        if not self._started:
            return

        self.scheduler.shutdown()
        self._started = False
        logger.info("Report scheduler stopped")

    def _is_email_configured(self) -> bool:
        """Check if email settings are configured"""
        return bool(
            self.settings.email_host and
            self.settings.email_user and
            self.settings.email_password
        )

    def _process_reports_job(self):
        """Background job to process pending reports"""
        logger.info("Starting scheduled report processing")
        db = SessionLocal()

        try:
            processor = ReportProcessor(db, self.settings.raw_reports_path)
            processed, failed = processor.process_pending_reports(limit=100)

            if processed > 0 or failed > 0:
                logger.info(
                    f"Scheduled processing complete: {processed} processed, {failed} failed"
                )
            else:
                logger.debug("No pending reports to process")

        except Exception as e:
            logger.error(f"Error in scheduled report processing: {str(e)}", exc_info=True)
        finally:
            db.close()

    def _ingest_emails_job(self):
        """Background job to check email for new reports"""
        logger.info("Starting scheduled email ingestion")
        db = SessionLocal()

        try:
            from app.services.ingestion import IngestionService

            service = IngestionService(db)
            stats = service.ingest_from_inbox(limit=50)

            logger.info(
                f"Email ingestion complete: {stats['attachments_ingested']} new reports from {stats['emails_checked']} emails",
                extra=stats
            )

        except Exception as e:
            logger.error(f"Error in scheduled email ingestion: {str(e)}", exc_info=True)
        finally:
            db.close()


# Global scheduler instance
_scheduler: Optional[ReportScheduler] = None


def get_scheduler() -> ReportScheduler:
    """Get or create the global scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = ReportScheduler()
    return _scheduler


def start_scheduler():
    """Start the global scheduler"""
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler():
    """Stop the global scheduler"""
    global _scheduler
    if _scheduler is not None:
        _scheduler.stop()
