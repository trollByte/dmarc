"""
Celery tasks for DMARC report processing.

These tasks handle parsing and storing DMARC reports in the database.
"""

import logging
from celery import Task
from app.celery_app import celery_app
from app.database import SessionLocal
from app.services.processing import ReportProcessor
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
    default_retry_delay=60,  # Retry after 60 seconds
    soft_time_limit=300,  # 5 minutes soft limit
    time_limit=600,  # 10 minutes hard limit
    name="app.tasks.processing.process_reports_task"
)
def process_reports_task(self, limit: int = 100):
    """
    Process pending DMARC reports.

    Args:
        limit: Maximum number of reports to process (default: 100)

    Returns:
        dict: Processing statistics (processed, failed counts)
    """
    logger.info(f"Starting Celery task: process_reports_task (limit={limit})")

    # Get database session
    db = SessionLocal()
    self._db = db  # Store for cleanup in after_return

    try:
        settings = get_settings()
        processor = ReportProcessor(db, settings.raw_reports_path)

        # Process pending reports
        processed, failed = processor.process_pending_reports(limit=limit)

        if processed > 0 or failed > 0:
            logger.info(
                f"Report processing complete: {processed} processed, {failed} failed"
            )
        else:
            logger.debug("No pending reports to process")

        # Invalidate caches after successful processing
        if processed > 0:
            from app.services.cache import get_cache
            cache = get_cache()
            if cache:
                cache.invalidate_pattern("timeline:*")
                cache.invalidate_pattern("summary:*")
                cache.invalidate_pattern("sources:*")
                cache.invalidate_pattern("domains:*")
                cache.invalidate_pattern("alignment:*")
                logger.debug("Cache invalidated after processing")

        return {
            "status": "success",
            "processed": processed,
            "failed": failed,
            "task_id": self.request.id
        }

    except Exception as e:
        logger.error(f"Error in process_reports_task: {str(e)}", exc_info=True)

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 60 * (2 ** self.request.retries)  # 60s, 120s, 240s
            logger.info(f"Retrying in {retry_delay}s (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=retry_delay)
        else:
            logger.error("Max retries reached, task failed permanently")
            return {
                "status": "failed",
                "error": str(e),
                "task_id": self.request.id
            }


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    max_retries=2,
    soft_time_limit=120,  # 2 minutes soft limit
    time_limit=180,  # 3 minutes hard limit
    name="app.tasks.processing.ingest_and_process_task"
)
def ingest_and_process_task(self, content: bytes, source: str):
    """
    Ingest and process a DMARC report from raw content.

    Used by bulk import for async processing.

    Args:
        content: Raw XML content (bytes)
        source: Source identifier (filename)

    Returns:
        dict: Processing result
    """
    logger.info(f"Ingesting and processing report: {source}")

    db = SessionLocal()
    self._db = db

    try:
        settings = get_settings()
        processor = ReportProcessor(db, settings.raw_reports_path)
        result = processor.process_report(content, source)

        if result:
            logger.info(f"Successfully processed report: {source}")
            return {"status": "success", "source": source}
        else:
            logger.info(f"Duplicate report skipped: {source}")
            return {"status": "duplicate", "source": source}

    except Exception as e:
        logger.error(f"Error processing report {source}: {str(e)}", exc_info=True)

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=30)
        else:
            return {"status": "failed", "error": str(e), "source": source}


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    max_retries=2,
    soft_time_limit=120,  # 2 minutes soft limit
    time_limit=180,  # 3 minutes hard limit
    name="app.tasks.processing.process_single_report_task"
)
def process_single_report_task(self, report_id: int):
    """
    Process a single DMARC report by ID.

    Useful for task chaining or manual processing.

    Args:
        report_id: IngestedReport ID to process

    Returns:
        dict: Processing result
    """
    logger.info(f"Processing single report: {report_id}")

    db = SessionLocal()
    self._db = db

    try:
        settings = get_settings()
        processor = ReportProcessor(db, settings.raw_reports_path)

        # Process the specific report
        from app.models import IngestedReport
        report = db.query(IngestedReport).filter(IngestedReport.id == report_id).first()

        if not report:
            logger.warning(f"Report {report_id} not found")
            return {"status": "error", "message": "Report not found"}

        if report.status == "completed":
            logger.info(f"Report {report_id} already processed")
            return {"status": "skipped", "message": "Already processed"}

        # Process it
        result = processor._process_single_report(report)

        if result:
            logger.info(f"Successfully processed report {report_id}")
            return {"status": "success", "report_id": report_id}
        else:
            logger.warning(f"Failed to process report {report_id}")
            return {"status": "failed", "report_id": report_id}

    except Exception as e:
        logger.error(f"Error processing report {report_id}: {str(e)}", exc_info=True)

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=30)
        else:
            return {"status": "failed", "error": str(e), "report_id": report_id}
