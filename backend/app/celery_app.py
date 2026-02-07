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
        "app.tasks.ml_tasks",
        "app.tasks.advisor_tasks",
        "app.tasks.scheduled_reports",
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
    beat_schedule_filename="/app/celery-data/celerybeat-schedule",
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
    # ML: Train anomaly detection model weekly (Sunday 2 AM)
    "train-anomaly-model-weekly": {
        "task": "app.tasks.ml_tasks.train_anomaly_model_task",
        "schedule": crontab(day_of_week=0, hour=2, minute=0),  # Sunday 2 AM
    },
    # ML: Detect anomalies daily (3 AM)
    "detect-anomalies-daily": {
        "task": "app.tasks.ml_tasks.detect_anomalies_task",
        "schedule": crontab(hour=3, minute=0),  # Daily 3 AM
    },
    # ML: Purge geolocation cache weekly (Monday 1 AM)
    "purge-geolocation-cache-weekly": {
        "task": "app.tasks.ml_tasks.purge_geolocation_cache_task",
        "schedule": crontab(day_of_week=1, hour=1, minute=0),  # Monday 1 AM
    },
    # ML: Generate analytics cache daily (4 AM)
    "generate-analytics-cache-daily": {
        "task": "app.tasks.ml_tasks.generate_analytics_cache_task",
        "schedule": crontab(hour=4, minute=0),  # Daily 4 AM
    },
    # Advisor: Send weekly report (Monday 8 AM)
    "send-weekly-advisor-report": {
        "task": "app.tasks.advisor_tasks.send_weekly_advisor_report",
        "schedule": crontab(day_of_week=1, hour=8, minute=0),  # Monday 8 AM
    },
    # Advisor: Send daily health summary (8 AM, only if critical issues)
    "send-daily-health-summary": {
        "task": "app.tasks.advisor_tasks.send_daily_health_summary",
        "schedule": crontab(hour=8, minute=0),  # Daily 8 AM
    },
    # Process scheduled reports every 15 minutes
    "process-scheduled-reports-every-15min": {
        "task": "app.tasks.scheduled_reports.process_scheduled_reports_task",
        "schedule": 900.0,  # 15 minutes in seconds
    },
}


if __name__ == "__main__":
    celery_app.start()
