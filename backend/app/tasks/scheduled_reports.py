"""
Celery tasks for scheduled report delivery.

These tasks handle periodic execution of scheduled DMARC reports.
"""

import logging
from celery import Task
from app.celery_app import celery_app
from app.database import SessionLocal
from app.config import get_settings

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task that manages database session lifecycle"""

    _db = None

    def after_return(self, *args, **kwargs):
        """Close database session after task completes"""
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    max_retries=2,
    default_retry_delay=300,  # Retry after 5 minutes
    soft_time_limit=600,  # 10 minutes soft limit
    time_limit=900,  # 15 minutes hard limit
    name="app.tasks.scheduled_reports.process_scheduled_reports_task"
)
def process_scheduled_reports_task(self):
    """
    Process all scheduled reports that are due to run.

    This task:
    1. Fetches all active schedules where next_run_at <= now
    2. Generates and sends each report
    3. Updates schedule tracking (last_run_at, next_run_at, run_count)

    Returns:
        dict: Processing statistics (schedules_found, successful, failed)
    """
    logger.info("Starting Celery task: process_scheduled_reports_task")

    settings = get_settings()

    # Check if SMTP is configured (required for report delivery)
    if not settings.smtp_host:
        logger.debug("SMTP not configured, skipping scheduled report delivery")
        return {
            "status": "skipped",
            "message": "SMTP not configured",
            "schedules_processed": 0
        }

    # Get database session
    db = SessionLocal()
    self._db = db

    try:
        from app.services.scheduled_reports_service import ScheduledReportsService

        service = ScheduledReportsService(db)

        # Get all schedules that are due
        due_schedules = service.get_due_schedules()

        if not due_schedules:
            logger.debug("No scheduled reports due")
            return {
                "status": "success",
                "schedules_found": 0,
                "successful": 0,
                "failed": 0,
                "task_id": self.request.id
            }

        logger.info(f"Found {len(due_schedules)} scheduled report(s) to process")

        successful = 0
        failed = 0

        # Process each schedule
        for schedule in due_schedules:
            try:
                logger.info(f"Processing schedule: {schedule.name} (id={schedule.id})")
                log = service.run_schedule(schedule)

                if log.status == "delivered":
                    successful += 1
                    logger.info(f"Successfully delivered report: {schedule.name}")
                else:
                    failed += 1
                    logger.warning(f"Failed to deliver report: {schedule.name} - {log.error_message}")

            except Exception as e:
                failed += 1
                logger.error(f"Error processing schedule {schedule.id}: {str(e)}", exc_info=True)

        logger.info(
            f"Scheduled reports processing complete: {successful} successful, {failed} failed",
            extra={
                "schedules_found": len(due_schedules),
                "successful": successful,
                "failed": failed
            }
        )

        return {
            "status": "success",
            "schedules_found": len(due_schedules),
            "successful": successful,
            "failed": failed,
            "task_id": self.request.id
        }

    except Exception as e:
        logger.error(f"Error in process_scheduled_reports_task: {str(e)}", exc_info=True)

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 300 * (2 ** self.request.retries)  # 5min, 10min
            logger.info(f"Retrying in {retry_delay}s (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=retry_delay)
        else:
            logger.error("Max retries reached, task failed permanently")
            return {
                "status": "failed",
                "error": str(e),
                "task_id": self.request.id
            }
