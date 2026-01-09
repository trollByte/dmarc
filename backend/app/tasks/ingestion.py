"""
Celery tasks for DMARC report ingestion from email.

These tasks handle fetching reports from IMAP mailboxes and storing them.
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
    max_retries=3,
    default_retry_delay=120,  # Retry after 2 minutes
    soft_time_limit=600,  # 10 minutes soft limit
    time_limit=900,  # 15 minutes hard limit
    name="app.tasks.ingestion.ingest_emails_task"
)
def ingest_emails_task(self, limit: int = 50):
    """
    Ingest DMARC reports from IMAP inbox.

    Args:
        limit: Maximum number of emails to process (default: 50)

    Returns:
        dict: Ingestion statistics (emails_checked, attachments_ingested, etc.)
    """
    logger.info(f"Starting Celery task: ingest_emails_task (limit={limit})")

    settings = get_settings()

    # Check if email is configured
    if not (settings.email_host and settings.email_user and settings.email_password):
        logger.warning("Email not configured, skipping ingestion")
        return {
            "status": "skipped",
            "message": "Email not configured",
            "emails_checked": 0,
            "attachments_ingested": 0
        }

    # Get database session
    db = SessionLocal()
    self._db = db

    try:
        from app.services.ingestion import IngestionService

        service = IngestionService(db)
        stats = service.ingest_from_inbox(limit=limit)

        logger.info(
            f"Email ingestion complete: {stats['attachments_ingested']} new reports from {stats['emails_checked']} emails",
            extra=stats
        )

        # If we ingested new reports, optionally chain to processing task
        if stats['attachments_ingested'] > 0 and settings.use_celery:
            # Chain to processing task
            from app.tasks.processing import process_reports_task
            process_reports_task.apply_async(
                kwargs={"limit": stats['attachments_ingested']},
                countdown=10  # Wait 10 seconds before processing
            )
            logger.info(f"Chained processing task for {stats['attachments_ingested']} reports")

        return {
            "status": "success",
            "task_id": self.request.id,
            **stats
        }

    except Exception as e:
        logger.error(f"Error in ingest_emails_task: {str(e)}", exc_info=True)

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 120 * (2 ** self.request.retries)  # 2min, 4min, 8min
            logger.info(f"Retrying in {retry_delay}s (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=retry_delay)
        else:
            logger.error("Max retries reached, task failed permanently")
            return {
                "status": "failed",
                "error": str(e),
                "task_id": self.request.id
            }
