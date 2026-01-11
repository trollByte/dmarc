"""
Scheduled Reports Service.

Manages scheduled report generation and delivery via email.

Features:
- Schedule daily/weekly/monthly reports
- Multiple report types (DMARC summary, domain details, threats)
- Email delivery with PDF attachments
- Report history tracking
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
from io import BytesIO

from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

from app.database import Base
from app.config import get_settings
import uuid

logger = logging.getLogger(__name__)
settings = get_settings()


class ReportFrequency(str, Enum):
    """Report frequency options"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ReportType(str, Enum):
    """Types of reports"""
    DMARC_SUMMARY = "dmarc_summary"
    DOMAIN_DETAIL = "domain_detail"
    THREAT_REPORT = "threat_report"
    COMPLIANCE_REPORT = "compliance_report"
    EXECUTIVE_SUMMARY = "executive_summary"


class DeliveryStatus(str, Enum):
    """Report delivery status"""
    PENDING = "pending"
    GENERATING = "generating"
    SENDING = "sending"
    DELIVERED = "delivered"
    FAILED = "failed"


@dataclass
class ReportConfig:
    """Report configuration"""
    report_type: ReportType
    domains: List[str]
    include_charts: bool
    include_recommendations: bool
    date_range_days: int


class ScheduledReport(Base):
    """Scheduled report configuration"""
    __tablename__ = "scheduled_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Owner
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Schedule
    frequency = Column(String(20), nullable=False)  # daily, weekly, monthly
    day_of_week = Column(Integer, nullable=True)  # 0-6 for weekly
    day_of_month = Column(Integer, nullable=True)  # 1-31 for monthly
    hour = Column(Integer, default=8, nullable=False)  # Hour to send (UTC)
    timezone = Column(String(50), default="UTC", nullable=False)

    # Report config
    report_type = Column(String(30), nullable=False)
    domains = Column(ARRAY(String), nullable=True)  # Specific domains or null for all
    date_range_days = Column(Integer, default=7, nullable=False)
    include_charts = Column(Boolean, default=True, nullable=False)
    include_recommendations = Column(Boolean, default=True, nullable=False)
    report_format = Column(String(10), default="pdf", nullable=False)

    # Delivery
    recipients = Column(ARRAY(String), nullable=False)
    email_subject = Column(String(255), nullable=True)
    email_body = Column(Text, nullable=True)

    # Tracking
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    run_count = Column(Integer, default=0, nullable=False)
    failure_count = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ScheduledReport(name={self.name}, frequency={self.frequency})>"


class ReportDeliveryLog(Base):
    """Log of report deliveries"""
    __tablename__ = "report_delivery_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scheduled_report_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Status
    status = Column(String(20), nullable=False, index=True)
    error_message = Column(Text, nullable=True)

    # Report details
    report_type = Column(String(30), nullable=False)
    date_range_start = Column(DateTime, nullable=False)
    date_range_end = Column(DateTime, nullable=False)
    domains_included = Column(ARRAY(String), nullable=True)

    # File info
    file_size_bytes = Column(Integer, nullable=True)
    generation_time_ms = Column(Integer, nullable=True)

    # Delivery
    recipients = Column(ARRAY(String), nullable=False)
    delivered_at = Column(DateTime, nullable=True)

    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<ReportDeliveryLog(id={self.id}, status={self.status})>"


class ScheduledReportsService:
    """Service for managing scheduled reports"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== Schedule Management ====================

    def create_schedule(
        self,
        user_id: uuid.UUID,
        name: str,
        frequency: str,
        report_type: str,
        recipients: List[str],
        domains: Optional[List[str]] = None,
        day_of_week: Optional[int] = None,
        day_of_month: Optional[int] = None,
        hour: int = 8,
        timezone: str = "UTC",
        date_range_days: int = 7,
        include_charts: bool = True,
        include_recommendations: bool = True,
        email_subject: Optional[str] = None,
        email_body: Optional[str] = None,
        description: Optional[str] = None,
    ) -> ScheduledReport:
        """Create a new scheduled report"""
        schedule = ScheduledReport(
            user_id=user_id,
            name=name,
            description=description,
            frequency=frequency,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            hour=hour,
            timezone=timezone,
            report_type=report_type,
            domains=domains,
            date_range_days=date_range_days,
            include_charts=include_charts,
            include_recommendations=include_recommendations,
            recipients=recipients,
            email_subject=email_subject,
            email_body=email_body,
            next_run_at=self._calculate_next_run(frequency, day_of_week, day_of_month, hour),
        )

        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)

        return schedule

    def update_schedule(
        self,
        schedule_id: uuid.UUID,
        user_id: uuid.UUID,
        **updates
    ) -> Optional[ScheduledReport]:
        """Update a scheduled report"""
        schedule = self.db.query(ScheduledReport).filter(
            ScheduledReport.id == schedule_id,
            ScheduledReport.user_id == user_id,
        ).first()

        if not schedule:
            return None

        for key, value in updates.items():
            if hasattr(schedule, key) and value is not None:
                setattr(schedule, key, value)

        # Recalculate next run if schedule changed
        if any(k in updates for k in ['frequency', 'day_of_week', 'day_of_month', 'hour']):
            schedule.next_run_at = self._calculate_next_run(
                schedule.frequency,
                schedule.day_of_week,
                schedule.day_of_month,
                schedule.hour,
            )

        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def delete_schedule(self, schedule_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete a scheduled report"""
        schedule = self.db.query(ScheduledReport).filter(
            ScheduledReport.id == schedule_id,
            ScheduledReport.user_id == user_id,
        ).first()

        if schedule:
            self.db.delete(schedule)
            self.db.commit()
            return True
        return False

    def get_schedules(
        self,
        user_id: Optional[uuid.UUID] = None,
        active_only: bool = True,
    ) -> List[ScheduledReport]:
        """Get scheduled reports"""
        query = self.db.query(ScheduledReport)

        if user_id:
            query = query.filter(ScheduledReport.user_id == user_id)
        if active_only:
            query = query.filter(ScheduledReport.is_active == True)

        return query.order_by(ScheduledReport.next_run_at).all()

    def get_schedule(self, schedule_id: uuid.UUID) -> Optional[ScheduledReport]:
        """Get a single schedule"""
        return self.db.query(ScheduledReport).filter(
            ScheduledReport.id == schedule_id
        ).first()

    # ==================== Execution ====================

    def get_due_schedules(self) -> List[ScheduledReport]:
        """Get schedules that are due to run"""
        now = datetime.utcnow()
        return self.db.query(ScheduledReport).filter(
            ScheduledReport.is_active == True,
            ScheduledReport.next_run_at <= now,
        ).all()

    def run_schedule(self, schedule: ScheduledReport) -> ReportDeliveryLog:
        """Execute a scheduled report"""
        from app.services.export_service import ExportService

        # Create log entry
        log = ReportDeliveryLog(
            scheduled_report_id=schedule.id,
            status=DeliveryStatus.GENERATING.value,
            report_type=schedule.report_type,
            date_range_start=datetime.utcnow() - timedelta(days=schedule.date_range_days),
            date_range_end=datetime.utcnow(),
            domains_included=schedule.domains,
            recipients=schedule.recipients,
        )
        self.db.add(log)
        self.db.commit()

        start_time = datetime.utcnow()

        try:
            # Generate report
            export_service = ExportService(self.db)
            report_data = self._generate_report_data(schedule)

            pdf_bytes = export_service.generate_pdf_report(
                title=f"{schedule.name} - {schedule.report_type}",
                data=report_data,
                include_charts=schedule.include_charts,
            )

            log.file_size_bytes = len(pdf_bytes)
            log.generation_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Send email
            log.status = DeliveryStatus.SENDING.value
            self.db.commit()

            self._send_email(
                recipients=schedule.recipients,
                subject=schedule.email_subject or f"Scheduled Report: {schedule.name}",
                body=schedule.email_body or self._default_email_body(schedule),
                attachment=pdf_bytes,
                attachment_name=f"{schedule.name}_{datetime.utcnow().strftime('%Y%m%d')}.pdf",
            )

            # Success
            log.status = DeliveryStatus.DELIVERED.value
            log.delivered_at = datetime.utcnow()
            log.completed_at = datetime.utcnow()

            schedule.last_run_at = datetime.utcnow()
            schedule.run_count += 1
            schedule.next_run_at = self._calculate_next_run(
                schedule.frequency,
                schedule.day_of_week,
                schedule.day_of_month,
                schedule.hour,
            )

        except Exception as e:
            logger.error(f"Failed to run scheduled report {schedule.id}: {e}")
            log.status = DeliveryStatus.FAILED.value
            log.error_message = str(e)
            log.completed_at = datetime.utcnow()
            schedule.failure_count += 1

        self.db.commit()
        return log

    def run_now(self, schedule_id: uuid.UUID, user_id: uuid.UUID) -> Optional[ReportDeliveryLog]:
        """Run a schedule immediately"""
        schedule = self.db.query(ScheduledReport).filter(
            ScheduledReport.id == schedule_id,
            ScheduledReport.user_id == user_id,
        ).first()

        if not schedule:
            return None

        return self.run_schedule(schedule)

    def _generate_report_data(self, schedule: ScheduledReport) -> Dict[str, Any]:
        """Generate report data based on type"""
        # This would integrate with analytics/reporting services
        # Placeholder implementation
        return {
            "report_type": schedule.report_type,
            "generated_at": datetime.utcnow().isoformat(),
            "date_range": {
                "start": (datetime.utcnow() - timedelta(days=schedule.date_range_days)).isoformat(),
                "end": datetime.utcnow().isoformat(),
            },
            "domains": schedule.domains or ["All domains"],
            "summary": {
                "total_reports": 0,
                "pass_rate": 0.0,
                "fail_count": 0,
            },
            "sections": [],
        }

    def _default_email_body(self, schedule: ScheduledReport) -> str:
        """Generate default email body"""
        return f"""
Hello,

Please find attached your scheduled {schedule.report_type.replace('_', ' ').title()} report.

Report Name: {schedule.name}
Frequency: {schedule.frequency.title()}
Date Range: Last {schedule.date_range_days} days
Domains: {', '.join(schedule.domains) if schedule.domains else 'All domains'}

This is an automated report generated by the DMARC Dashboard.

Best regards,
DMARC Dashboard
        """.strip()

    def _send_email(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        attachment: bytes,
        attachment_name: str,
    ):
        """Send email with PDF attachment"""
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = settings.smtp_from or "noreply@example.com"
        msg['To'] = ", ".join(recipients)

        # Body
        msg.attach(MIMEText(body, 'plain'))

        # Attachment
        pdf_attachment = MIMEApplication(attachment, Name=attachment_name)
        pdf_attachment['Content-Disposition'] = f'attachment; filename="{attachment_name}"'
        msg.attach(pdf_attachment)

        # Send
        if settings.smtp_host:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port or 587) as server:
                if settings.smtp_username and settings.smtp_password:
                    server.starttls()
                    server.login(settings.smtp_username, settings.smtp_password)
                server.sendmail(msg['From'], recipients, msg.as_string())
        else:
            logger.warning("SMTP not configured, skipping email delivery")

    def _calculate_next_run(
        self,
        frequency: str,
        day_of_week: Optional[int],
        day_of_month: Optional[int],
        hour: int,
    ) -> datetime:
        """Calculate next run time"""
        now = datetime.utcnow()
        next_run = now.replace(hour=hour, minute=0, second=0, microsecond=0)

        if frequency == ReportFrequency.DAILY.value:
            if next_run <= now:
                next_run += timedelta(days=1)

        elif frequency == ReportFrequency.WEEKLY.value:
            target_day = day_of_week or 0  # Default to Monday
            days_ahead = target_day - now.weekday()
            if days_ahead <= 0 or (days_ahead == 0 and next_run <= now):
                days_ahead += 7
            next_run += timedelta(days=days_ahead)

        elif frequency == ReportFrequency.MONTHLY.value:
            target_day = day_of_month or 1
            next_run = next_run.replace(day=min(target_day, 28))  # Safe day
            if next_run <= now:
                # Move to next month
                if next_run.month == 12:
                    next_run = next_run.replace(year=next_run.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=next_run.month + 1)

        return next_run

    # ==================== History ====================

    def get_delivery_logs(
        self,
        schedule_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        days: int = 30,
        limit: int = 100,
    ) -> List[ReportDeliveryLog]:
        """Get delivery logs"""
        since = datetime.utcnow() - timedelta(days=days)
        query = self.db.query(ReportDeliveryLog).filter(
            ReportDeliveryLog.started_at >= since
        )

        if schedule_id:
            query = query.filter(ReportDeliveryLog.scheduled_report_id == schedule_id)
        if status:
            query = query.filter(ReportDeliveryLog.status == status)

        return query.order_by(ReportDeliveryLog.started_at.desc()).limit(limit).all()
