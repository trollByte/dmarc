"""
Celery tasks for DMARC alerting.

These tasks handle checking alert conditions and sending notifications.
"""

import logging
from celery import Task
from typing import Optional
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
    default_retry_delay=180,  # Retry after 3 minutes
    soft_time_limit=180,  # 3 minutes soft limit
    time_limit=300,  # 5 minutes hard limit
    name="app.tasks.alerting.check_alerts_task"
)
def check_alerts_task(self, domain: Optional[str] = None):
    """
    Check DMARC alert conditions and send notifications.

    Args:
        domain: Optional domain to check alerts for (None = all domains)

    Returns:
        dict: Alert statistics (alerts_triggered, notifications_sent, etc.)
    """
    logger.info(f"Starting Celery task: check_alerts_task (domain={domain or 'all'})")

    settings = get_settings()

    # Check if alerting is enabled
    if not settings.enable_alerts:
        logger.debug("Alerting is disabled, skipping alert check")
        return {
            "status": "skipped",
            "message": "Alerting is disabled",
            "alerts_triggered": 0
        }

    # Get database session
    db = SessionLocal()
    self._db = db

    try:
        from app.services.alerting import AlertService
        from app.services.notifications import NotificationService

        # Check alerts
        alert_service = AlertService(db)
        alerts = alert_service.check_all_alerts(domain=domain)

        if alerts:
            logger.info(f"Found {len(alerts)} alert(s) to send")

            # Send notifications
            notification_service = NotificationService()
            stats = notification_service.send_alerts(alerts)

            logger.info(
                f"Alert notification complete: {stats['sent']} sent, {stats['failed']} failed",
                extra=stats
            )

            return {
                "status": "success",
                "alerts_triggered": len(alerts),
                "notifications_sent": stats['sent'],
                "notifications_failed": stats['failed'],
                "channels": stats.get('channels', {}),
                "task_id": self.request.id
            }
        else:
            logger.debug("No alerts triggered")
            return {
                "status": "success",
                "alerts_triggered": 0,
                "notifications_sent": 0,
                "task_id": self.request.id
            }

    except Exception as e:
        logger.error(f"Error in check_alerts_task: {str(e)}", exc_info=True)

        # Retry with backoff
        if self.request.retries < self.max_retries:
            retry_delay = 180 * (2 ** self.request.retries)  # 3min, 6min
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
    soft_time_limit=60,  # 1 minute soft limit
    time_limit=120,  # 2 minutes hard limit
    name="app.tasks.alerting.send_notification_task"
)
def send_notification_task(self, alert_data: dict, channel: str):
    """
    Send a single notification to a specific channel.

    Useful for parallel notification dispatch.

    Args:
        alert_data: Alert information dictionary
        channel: Notification channel ('email', 'slack', 'discord', 'teams')

    Returns:
        dict: Notification result
    """
    logger.info(f"Sending notification to {channel}")

    try:
        from app.services.notifications import NotificationService
        from app.services.alerting import Alert

        # Reconstruct Alert object from dict
        alert = Alert(
            alert_type=alert_data['alert_type'],
            severity=alert_data['severity'],
            title=alert_data['title'],
            message=alert_data['message'],
            details=alert_data.get('details', {})
        )

        notification_service = NotificationService()

        # Send to specific channel
        if channel == 'email':
            notification_service.send_email_alerts([alert])
        elif channel == 'slack':
            notification_service.send_slack_alerts([alert])
        elif channel == 'discord':
            notification_service.send_discord_alerts([alert])
        elif channel == 'teams':
            notification_service.send_teams_alerts([alert])
        else:
            logger.warning(f"Unknown channel: {channel}")
            return {"status": "error", "message": f"Unknown channel: {channel}"}

        logger.info(f"Successfully sent notification to {channel}")
        return {"status": "success", "channel": channel}

    except Exception as e:
        logger.error(f"Error sending notification to {channel}: {str(e)}", exc_info=True)
        return {"status": "failed", "channel": channel, "error": str(e)}
