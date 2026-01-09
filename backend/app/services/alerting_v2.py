"""
Enhanced alert service with persistence and deduplication.

Features:
- Alert deduplication via SHA256 fingerprinting
- Alert lifecycle tracking (created → acknowledged → resolved)
- Configurable alert rules
- Time-based alert suppressions
- Cooldown periods to prevent alert spam
- Integration with notification service (Teams priority)
"""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.models import (
    AlertHistory, AlertRule, AlertSuppression,
    AlertSeverity, AlertType, AlertStatus
)
from app.services.notifications import NotificationService

logger = logging.getLogger(__name__)


class EnhancedAlertService:
    """
    Enhanced alert service with persistence and deduplication.

    Replaces the original AlertingService with database-backed alerts.
    """

    def __init__(self, db: Session):
        self.db = db
        self.notification_service = NotificationService()

    # ==================== Alert Creation ====================

    def create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        message: str,
        domain: Optional[str] = None,
        current_value: Optional[float] = None,
        threshold_value: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> Optional[AlertHistory]:
        """
        Create a new alert with deduplication.

        Args:
            alert_type: Type of alert
            severity: Severity level
            title: Alert title
            message: Alert message
            domain: Domain (if applicable)
            current_value: Current metric value
            threshold_value: Threshold that was exceeded
            metadata: Additional context
            force: Skip deduplication and cooldown checks

        Returns:
            AlertHistory object if created, None if deduplicated/suppressed
        """
        # Generate fingerprint for deduplication
        fingerprint = self._generate_fingerprint(
            alert_type, domain or "", current_value or 0, threshold_value or 0
        )

        # Check if suppressed
        if not force and self._is_suppressed(alert_type, severity, domain):
            logger.info(
                f"Alert suppressed: {alert_type.value} for {domain or 'all domains'}",
                extra={"fingerprint": fingerprint}
            )
            return None

        # Check for existing alert in cooldown period
        if not force:
            cooldown_minutes = self._get_cooldown_minutes(alert_type)
            existing = self._find_recent_alert(fingerprint, cooldown_minutes)

            if existing:
                logger.info(
                    f"Alert deduplicated (cooldown): {alert_type.value}",
                    extra={
                        "fingerprint": fingerprint,
                        "existing_id": str(existing.id),
                        "cooldown_until": existing.cooldown_until
                    }
                )
                return None

        # Create new alert
        alert = AlertHistory(
            alert_type=alert_type,
            severity=severity,
            fingerprint=fingerprint,
            title=title,
            message=message,
            domain=domain,
            current_value=current_value,
            threshold_value=threshold_value,
            alert_metadata=metadata or {},
            status=AlertStatus.CREATED,
            cooldown_until=datetime.utcnow() + timedelta(minutes=self._get_cooldown_minutes(alert_type))
        )

        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)

        logger.info(
            f"Alert created: {alert_type.value} ({severity.value})",
            extra={
                "alert_id": str(alert.id),
                "fingerprint": fingerprint,
                "domain": domain
            }
        )

        # Send notifications
        self._send_notifications(alert)

        return alert

    # ==================== Alert Lifecycle ====================

    def acknowledge_alert(
        self,
        alert_id: str,
        user_id: str,
        note: Optional[str] = None
    ) -> AlertHistory:
        """
        Acknowledge an alert.

        Args:
            alert_id: Alert UUID
            user_id: User UUID who acknowledged
            note: Optional acknowledgement note

        Returns:
            Updated AlertHistory

        Raises:
            ValueError: If alert not found or already acknowledged
        """
        alert = self.db.query(AlertHistory).filter(AlertHistory.id == alert_id).first()
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        if alert.status != AlertStatus.CREATED:
            raise ValueError(f"Alert already {alert.status.value}")

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = user_id
        alert.acknowledgement_note = note

        self.db.commit()
        self.db.refresh(alert)

        logger.info(
            f"Alert acknowledged: {alert.alert_type.value}",
            extra={"alert_id": str(alert.id), "user_id": user_id}
        )

        return alert

    def resolve_alert(
        self,
        alert_id: str,
        user_id: str,
        note: Optional[str] = None
    ) -> AlertHistory:
        """
        Resolve an alert.

        Args:
            alert_id: Alert UUID
            user_id: User UUID who resolved
            note: Optional resolution note

        Returns:
            Updated AlertHistory

        Raises:
            ValueError: If alert not found or already resolved
        """
        alert = self.db.query(AlertHistory).filter(AlertHistory.id == alert_id).first()
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        if alert.status == AlertStatus.RESOLVED:
            raise ValueError("Alert already resolved")

        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        alert.resolved_by = user_id
        alert.resolution_note = note

        self.db.commit()
        self.db.refresh(alert)

        logger.info(
            f"Alert resolved: {alert.alert_type.value}",
            extra={"alert_id": str(alert.id), "user_id": user_id}
        )

        return alert

    # ==================== Alert Queries ====================

    def get_active_alerts(
        self,
        domain: Optional[str] = None,
        severity: Optional[AlertSeverity] = None,
        limit: int = 100
    ) -> List[AlertHistory]:
        """Get active (created or acknowledged) alerts"""
        query = self.db.query(AlertHistory).filter(
            AlertHistory.status.in_([AlertStatus.CREATED, AlertStatus.ACKNOWLEDGED])
        )

        if domain:
            query = query.filter(AlertHistory.domain == domain)

        if severity:
            query = query.filter(AlertHistory.severity == severity)

        return query.order_by(AlertHistory.created_at.desc()).limit(limit).all()

    def get_alert_history(
        self,
        domain: Optional[str] = None,
        alert_type: Optional[AlertType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AlertHistory]:
        """Get historical alerts with filters"""
        query = self.db.query(AlertHistory)

        if domain:
            query = query.filter(AlertHistory.domain == domain)

        if alert_type:
            query = query.filter(AlertHistory.alert_type == alert_type)

        if start_date:
            query = query.filter(AlertHistory.created_at >= start_date)

        if end_date:
            query = query.filter(AlertHistory.created_at <= end_date)

        return query.order_by(AlertHistory.created_at.desc()).limit(limit).all()

    def get_alert_stats(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get alert statistics for the past N days"""
        since = datetime.utcnow() - timedelta(days=days)

        alerts = self.db.query(AlertHistory).filter(
            AlertHistory.created_at >= since
        ).all()

        stats = {
            "period_days": days,
            "total_alerts": len(alerts),
            "by_severity": {},
            "by_type": {},
            "by_status": {},
            "by_domain": {},
            "avg_resolution_time_hours": None
        }

        # Group by severity
        for severity in AlertSeverity:
            count = sum(1 for a in alerts if a.severity == severity)
            stats["by_severity"][severity.value] = count

        # Group by type
        for alert_type in AlertType:
            count = sum(1 for a in alerts if a.alert_type == alert_type)
            stats["by_type"][alert_type.value] = count

        # Group by status
        for status in AlertStatus:
            count = sum(1 for a in alerts if a.status == status)
            stats["by_status"][status.value] = count

        # Top domains
        domain_counts = {}
        for alert in alerts:
            if alert.domain:
                domain_counts[alert.domain] = domain_counts.get(alert.domain, 0) + 1

        stats["by_domain"] = dict(sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10])

        # Average resolution time
        resolved_alerts = [a for a in alerts if a.resolved_at and a.created_at]
        if resolved_alerts:
            total_seconds = sum(
                (a.resolved_at - a.created_at).total_seconds()
                for a in resolved_alerts
            )
            avg_seconds = total_seconds / len(resolved_alerts)
            stats["avg_resolution_time_hours"] = round(avg_seconds / 3600, 2)

        return stats

    # ==================== Alert Rules ====================

    def get_active_rules(self) -> List[AlertRule]:
        """Get all enabled alert rules"""
        return self.db.query(AlertRule).filter(AlertRule.is_enabled == True).all()

    def evaluate_rules(
        self,
        domain: str,
        metrics: Dict[str, float]
    ) -> List[AlertHistory]:
        """
        Evaluate alert rules against current metrics.

        Args:
            domain: Domain being evaluated
            metrics: Dictionary of metric values (e.g., {"failure_rate": 15.5})

        Returns:
            List of created alerts
        """
        rules = self.get_active_rules()
        created_alerts = []

        for rule in rules:
            # Check if rule applies to this domain
            if rule.domain_pattern:
                if rule.domain_pattern != domain:
                    # Simple wildcard check
                    if not (rule.domain_pattern.startswith("*.") and
                            domain.endswith(rule.domain_pattern[2:])):
                        continue

            # Evaluate rule conditions
            alert = self._evaluate_rule(rule, domain, metrics)
            if alert:
                created_alerts.append(alert)

        return created_alerts

    def _evaluate_rule(
        self,
        rule: AlertRule,
        domain: str,
        metrics: Dict[str, float]
    ) -> Optional[AlertHistory]:
        """Evaluate a single rule"""
        conditions = rule.conditions

        # Match rule type to metric
        if rule.alert_type == AlertType.FAILURE_RATE:
            metric_value = metrics.get("failure_rate")
            if metric_value is None:
                return None

            threshold = conditions.get("failure_rate", {}).get(rule.severity.value)
            if threshold and metric_value >= threshold:
                return self.create_alert(
                    alert_type=AlertType.FAILURE_RATE,
                    severity=rule.severity,
                    title=f"{rule.severity.value.upper()}: High failure rate for {domain}",
                    message=f"DMARC failure rate is {metric_value:.1f}% (threshold: {threshold}%)",
                    domain=domain,
                    current_value=metric_value,
                    threshold_value=threshold,
                    alert_metadata={"rule_id": str(rule.id), "rule_name": rule.name}
                )

        elif rule.alert_type == AlertType.VOLUME_SPIKE:
            metric_value = metrics.get("volume_change_percent")
            if metric_value is None:
                return None

            threshold = conditions.get("volume_spike", {}).get(rule.severity.value)
            if threshold and metric_value >= threshold:
                return self.create_alert(
                    alert_type=AlertType.VOLUME_SPIKE,
                    severity=rule.severity,
                    title=f"{rule.severity.value.upper()}: Volume spike for {domain}",
                    message=f"Email volume increased by {metric_value:.1f}% (threshold: {threshold}%)",
                    domain=domain,
                    current_value=metric_value,
                    threshold_value=threshold,
                    alert_metadata={"rule_id": str(rule.id), "rule_name": rule.name}
                )

        elif rule.alert_type == AlertType.VOLUME_DROP:
            metric_value = metrics.get("volume_change_percent")
            if metric_value is None:
                return None

            threshold = conditions.get("volume_drop", {}).get(rule.severity.value)
            if threshold and metric_value <= -abs(threshold):  # Negative threshold
                return self.create_alert(
                    alert_type=AlertType.VOLUME_DROP,
                    severity=rule.severity,
                    title=f"{rule.severity.value.upper()}: Volume drop for {domain}",
                    message=f"Email volume decreased by {abs(metric_value):.1f}% (threshold: {abs(threshold)}%)",
                    domain=domain,
                    current_value=metric_value,
                    threshold_value=-abs(threshold),
                    alert_metadata={"rule_id": str(rule.id), "rule_name": rule.name}
                )

        return None

    # ==================== Alert Suppressions ====================

    def _is_suppressed(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        domain: Optional[str] = None
    ) -> bool:
        """Check if alert should be suppressed"""
        suppressions = self.db.query(AlertSuppression).filter(
            AlertSuppression.is_active == True
        ).all()

        for suppression in suppressions:
            if suppression.matches_alert(alert_type, severity, domain):
                return True

        return False

    # ==================== Helper Methods ====================

    def _generate_fingerprint(
        self,
        alert_type: AlertType,
        domain: str,
        current_value: float,
        threshold_value: float
    ) -> str:
        """Generate SHA256 fingerprint for deduplication"""
        # Fingerprint includes: type + domain + threshold (not current value)
        # This allows same alert type/domain/threshold to deduplicate
        data = f"{alert_type.value}:{domain}:{threshold_value}"
        return hashlib.sha256(data.encode()).hexdigest()

    def _find_recent_alert(
        self,
        fingerprint: str,
        minutes: int
    ) -> Optional[AlertHistory]:
        """Find recent alert with same fingerprint within cooldown period"""
        cooldown_time = datetime.utcnow() - timedelta(minutes=minutes)

        return self.db.query(AlertHistory).filter(
            AlertHistory.fingerprint == fingerprint,
            AlertHistory.created_at >= cooldown_time
        ).order_by(AlertHistory.created_at.desc()).first()

    def _get_cooldown_minutes(self, alert_type: AlertType) -> int:
        """Get cooldown period for alert type from rules or default"""
        rule = self.db.query(AlertRule).filter(
            AlertRule.alert_type == alert_type,
            AlertRule.is_enabled == True
        ).first()

        if rule and rule.cooldown_minutes:
            return rule.cooldown_minutes

        # Default cooldowns by type
        defaults = {
            AlertType.FAILURE_RATE: 60,      # 1 hour
            AlertType.VOLUME_SPIKE: 120,     # 2 hours
            AlertType.VOLUME_DROP: 120,      # 2 hours
            AlertType.NEW_SOURCE: 1440,      # 24 hours
            AlertType.POLICY_VIOLATION: 60,  # 1 hour
            AlertType.ANOMALY: 180,          # 3 hours
        }

        return defaults.get(alert_type, 60)

    def _send_notifications(self, alert: AlertHistory) -> None:
        """Send notifications for alert via configured channels"""
        try:
            # Determine which channels to use
            rule = self.db.query(AlertRule).filter(
                AlertRule.alert_type == alert.alert_type,
                AlertRule.is_enabled == True
            ).first()

            channels = []

            # Teams notification (priority)
            if not rule or rule.notify_teams:
                teams_sent = self.notification_service.send_teams_alert(
                    alert.title,
                    alert.message,
                    alert.severity.value,
                    alert.domain,
                    metadata=alert.alert_metadata
                )
                if teams_sent:
                    channels.append("teams")

            # Email notification
            if not rule or rule.notify_email:
                email_sent = self.notification_service.send_email_alert(
                    alert.title,
                    alert.message,
                    alert.severity.value,
                    alert.domain
                )
                if email_sent:
                    channels.append("email")

            # Slack notification
            if rule and rule.notify_slack:
                slack_sent = self.notification_service.send_slack_alert(
                    alert.title,
                    alert.message,
                    alert.severity.value
                )
                if slack_sent:
                    channels.append("slack")

            # Update alert with notification status
            alert.notification_sent = len(channels) > 0
            alert.notification_sent_at = datetime.utcnow()
            alert.notification_channels = channels
            self.db.commit()

            logger.info(
                f"Notifications sent for alert {alert.id}",
                extra={"channels": channels}
            )

        except Exception as e:
            logger.error(
                f"Failed to send notifications for alert {alert.id}: {e}",
                exc_info=True
            )
