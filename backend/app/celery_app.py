"""
Celery application initialization and configuration.

This module sets up the Celery app for distributed task processing.
Tasks are discovered automatically from the app.tasks module.
"""

from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

# Construct result backend URL (sqlalchemy + database_url)
result_backend = f"db+{settings.database_url}" if settings.database_url else ""

# Initialize Celery app
celery_app = Celery(
    "dmarc_processor",
    broker=settings.celery_broker_url,
    backend=result_backend,
    include=[
        "app.tasks.ingestion",
        "app.tasks.processing",
        "app.tasks.alerting",
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=settings.celery_task_track_started,
    task_time_limit=settings.celery_task_time_limit,
    worker_prefetch_multiplier=settings.celery_worker_prefetch_multiplier,
    result_expires=3600,  # Results expire after 1 hour
)

# Celery Beat schedule (periodic tasks)
celery_app.conf.beat_schedule = {
    # Process pending reports every 5 minutes
    "process-reports-every-5min": {
        "task": "app.tasks.processing.process_reports_task",
        "schedule": 300.0,  # 5 minutes in seconds
    },
    # Ingest emails every 15 minutes (if email configured)
    "ingest-emails-every-15min": {
        "task": "app.tasks.ingestion.ingest_emails_task",
        "schedule": 900.0,  # 15 minutes in seconds
    },
    # Check alerts every hour
    "check-alerts-hourly": {
        "task": "app.tasks.alerting.check_alerts_task",
        "schedule": crontab(minute=0),  # Every hour on the hour
    },
}


if __name__ == "__main__":
    celery_app.start()
