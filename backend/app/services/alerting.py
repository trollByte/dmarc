"""
Alerting service for DMARC monitoring

Monitors DMARC data and sends notifications when thresholds are exceeded:
- High failure rates
- New/unknown source IPs
- Volume spikes or drops
- Policy violations
"""
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models import DmarcReport, DmarcRecord
from app.config import get_settings

logger = logging.getLogger(__name__)


class Alert:
    """Represents an alert condition that was triggered"""

    def __init__(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        details: Dict = None
    ):
        self.alert_type = alert_type
        self.severity = severity  # info, warning, critical
        self.title = title
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.utcnow()


class AlertService:
    """Service for monitoring DMARC data and triggering alerts"""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.alerts: List[Alert] = []

    def check_all_alerts(self, domain: Optional[str] = None) -> List[Alert]:
        """
        Check all alert conditions

        Args:
            domain: Optional domain to check (None = all domains)

        Returns:
            List of triggered alerts
        """
        self.alerts = []

        logger.info(f"Running alert checks for domain: {domain or 'all'}")

        # Check various alert conditions
        self.check_failure_rate(domain)
        self.check_new_sources(domain)
        self.check_volume_anomalies(domain)

        logger.info(f"Alert check complete: {len(self.alerts)} alerts triggered")

        return self.alerts

    def check_failure_rate(self, domain: Optional[str] = None):
        """
        Check if DMARC failure rate exceeds threshold

        Default threshold: 10% failures triggers warning, 25% triggers critical
        """
        try:
            # Get data from last 24 hours
            cutoff = datetime.utcnow() - timedelta(hours=24)

            query = self.db.query(DmarcReport).filter(
                DmarcReport.date_end >= cutoff
            )

            if domain:
                query = query.filter(DmarcReport.domain == domain)

            reports = query.all()

            if not reports:
                return

            # Get report IDs
            report_ids = [r.id for r in reports]

            # Single aggregation query instead of N+1
            from sqlalchemy import func, case, and_
            stats = self.db.query(
                func.sum(DmarcRecord.count).label('total'),
                func.sum(
                    case(
                        (and_(DmarcRecord.dkim_result == 'pass',
                              DmarcRecord.spf_result == 'pass'),
                         DmarcRecord.count),
                        else_=0
                    )
                ).label('passed')
            ).filter(DmarcRecord.report_id.in_(report_ids)).one()

            total_messages = stats.total or 0
            pass_count = stats.passed or 0

            if total_messages == 0:
                return

            fail_count = total_messages - pass_count
            failure_rate = (fail_count / total_messages) * 100

            # Check thresholds
            warning_threshold = getattr(self.settings, 'alert_failure_warning', 10.0)
            critical_threshold = getattr(self.settings, 'alert_failure_critical', 25.0)

            if failure_rate >= critical_threshold:
                self.alerts.append(Alert(
                    alert_type='failure_rate',
                    severity='critical',
                    title=f'Critical: High DMARC Failure Rate',
                    message=f'DMARC failure rate is {failure_rate:.1f}% (threshold: {critical_threshold}%)',
                    details={
                        'domain': domain or 'all',
                        'failure_rate': round(failure_rate, 2),
                        'total_messages': total_messages,
                        'failed_messages': fail_count,
                        'period_hours': 24
                    }
                ))
            elif failure_rate >= warning_threshold:
                self.alerts.append(Alert(
                    alert_type='failure_rate',
                    severity='warning',
                    title=f'Warning: Elevated DMARC Failure Rate',
                    message=f'DMARC failure rate is {failure_rate:.1f}% (threshold: {warning_threshold}%)',
                    details={
                        'domain': domain or 'all',
                        'failure_rate': round(failure_rate, 2),
                        'total_messages': total_messages,
                        'failed_messages': fail_count,
                        'period_hours': 24
                    }
                ))

        except Exception as e:
            logger.error(f"Error checking failure rate: {str(e)}", exc_info=True)

    def check_new_sources(self, domain: Optional[str] = None):
        """
        Check for new/unknown source IPs in the last 24 hours

        Alerts if new source IPs appear that weren't seen in the previous week
        """
        try:
            now = datetime.utcnow()
            recent_cutoff = now - timedelta(hours=24)
            historical_cutoff = now - timedelta(days=7)

            # Get recent source IPs (last 24h)
            recent_query = self.db.query(DmarcRecord.source_ip).join(
                DmarcReport
            ).filter(
                DmarcReport.date_end >= recent_cutoff
            )

            if domain:
                recent_query = recent_query.filter(DmarcReport.domain == domain)

            recent_ips = set(ip[0] for ip in recent_query.distinct().all())

            if not recent_ips:
                return

            # Get historical source IPs (last week, excluding last 24h)
            historical_query = self.db.query(DmarcRecord.source_ip).join(
                DmarcReport
            ).filter(
                and_(
                    DmarcReport.date_end >= historical_cutoff,
                    DmarcReport.date_end < recent_cutoff
                )
            )

            if domain:
                historical_query = historical_query.filter(DmarcReport.domain == domain)

            historical_ips = set(ip[0] for ip in historical_query.distinct().all())

            # Find new IPs
            new_ips = recent_ips - historical_ips

            if new_ips:
                # Get details about new IPs with single query
                ip_counts = self.db.query(
                    DmarcRecord.source_ip,
                    func.sum(DmarcRecord.count).label('count')
                ).join(
                    DmarcReport
                ).filter(
                    and_(
                        DmarcRecord.source_ip.in_(new_ips),
                        DmarcReport.date_end >= recent_cutoff
                    )
                ).group_by(DmarcRecord.source_ip).all()

                ip_details = [{'ip': ip, 'message_count': count} for ip, count in ip_counts]

                total_new_messages = sum(d['message_count'] for d in ip_details)

                self.alerts.append(Alert(
                    alert_type='new_sources',
                    severity='info',
                    title=f'New Source IPs Detected',
                    message=f'{len(new_ips)} new source IP(s) detected in the last 24 hours',
                    details={
                        'domain': domain or 'all',
                        'new_ip_count': len(new_ips),
                        'new_ips': ip_details[:10],  # Limit to top 10
                        'total_messages': total_new_messages
                    }
                ))

        except Exception as e:
            logger.error(f"Error checking new sources: {str(e)}", exc_info=True)

    def check_volume_anomalies(self, domain: Optional[str] = None):
        """
        Check for sudden volume spikes or drops

        Compares last 24h volume to average of previous week
        """
        try:
            now = datetime.utcnow()
            recent_cutoff = now - timedelta(hours=24)
            week_cutoff = now - timedelta(days=7)

            # Get recent volume (last 24h)
            recent_query = self.db.query(
                func.sum(DmarcRecord.count)
            ).join(DmarcReport).filter(
                DmarcReport.date_end >= recent_cutoff
            )

            if domain:
                recent_query = recent_query.filter(DmarcReport.domain == domain)

            recent_volume = recent_query.scalar() or 0

            # Get historical average (previous week, per day)
            historical_query = self.db.query(
                func.sum(DmarcRecord.count)
            ).join(DmarcReport).filter(
                and_(
                    DmarcReport.date_end >= week_cutoff,
                    DmarcReport.date_end < recent_cutoff
                )
            )

            if domain:
                historical_query = historical_query.filter(DmarcReport.domain == domain)

            historical_volume = historical_query.scalar() or 0
            avg_daily_volume = historical_volume / 6  # 6 days

            if avg_daily_volume == 0:
                return

            # Calculate percentage change
            change_pct = ((recent_volume - avg_daily_volume) / avg_daily_volume) * 100

            # Alert on significant changes (>50% increase or >30% decrease)
            spike_threshold = getattr(self.settings, 'alert_volume_spike', 50.0)
            drop_threshold = getattr(self.settings, 'alert_volume_drop', -30.0)

            if change_pct >= spike_threshold:
                self.alerts.append(Alert(
                    alert_type='volume_spike',
                    severity='warning',
                    title=f'Volume Spike Detected',
                    message=f'Email volume increased by {change_pct:.1f}% compared to daily average',
                    details={
                        'domain': domain or 'all',
                        'recent_volume': recent_volume,
                        'average_volume': int(avg_daily_volume),
                        'change_percent': round(change_pct, 1),
                        'period_hours': 24
                    }
                ))
            elif change_pct <= drop_threshold:
                self.alerts.append(Alert(
                    alert_type='volume_drop',
                    severity='warning',
                    title=f'Volume Drop Detected',
                    message=f'Email volume decreased by {abs(change_pct):.1f}% compared to daily average',
                    details={
                        'domain': domain or 'all',
                        'recent_volume': recent_volume,
                        'average_volume': int(avg_daily_volume),
                        'change_percent': round(change_pct, 1),
                        'period_hours': 24
                    }
                ))

        except Exception as e:
            logger.error(f"Error checking volume anomalies: {str(e)}", exc_info=True)
