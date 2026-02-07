"""Unit tests for ScheduledReportsService (scheduled_reports_service.py)"""
import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, PropertyMock

from app.services.scheduled_reports_service import (
    ScheduledReportsService,
    ScheduledReport,
    ReportDeliveryLog,
    ReportFrequency,
    ReportType,
    DeliveryStatus,
)


@pytest.mark.unit
class TestCreateSchedule:
    """Test creating scheduled reports"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return ScheduledReportsService(mock_db)

    def test_create_schedule_daily(self, service, mock_db):
        """Test creating a daily scheduled report"""
        user_id = uuid.uuid4()
        schedule = service.create_schedule(
            user_id=user_id,
            name="Daily DMARC Summary",
            frequency=ReportFrequency.DAILY.value,
            report_type=ReportType.DMARC_SUMMARY.value,
            recipients=["admin@example.com"],
            hour=8,
        )

        assert mock_db.add.called
        assert mock_db.commit.called
        assert mock_db.refresh.called

        added = mock_db.add.call_args[0][0]
        assert added.name == "Daily DMARC Summary"
        assert added.frequency == "daily"
        assert added.report_type == "dmarc_summary"
        assert added.recipients == ["admin@example.com"]
        assert added.user_id == user_id
        assert added.hour == 8

    def test_create_schedule_weekly_with_day(self, service, mock_db):
        """Test creating a weekly scheduled report with specific day"""
        schedule = service.create_schedule(
            user_id=uuid.uuid4(),
            name="Weekly Report",
            frequency=ReportFrequency.WEEKLY.value,
            report_type=ReportType.THREAT_REPORT.value,
            recipients=["security@example.com"],
            day_of_week=0,  # Monday
        )

        added = mock_db.add.call_args[0][0]
        assert added.frequency == "weekly"
        assert added.day_of_week == 0

    def test_create_schedule_monthly(self, service, mock_db):
        """Test creating a monthly scheduled report"""
        schedule = service.create_schedule(
            user_id=uuid.uuid4(),
            name="Monthly Executive Summary",
            frequency=ReportFrequency.MONTHLY.value,
            report_type=ReportType.EXECUTIVE_SUMMARY.value,
            recipients=["ciso@example.com", "cto@example.com"],
            day_of_month=1,
            include_charts=True,
            include_recommendations=True,
            date_range_days=30,
        )

        added = mock_db.add.call_args[0][0]
        assert added.frequency == "monthly"
        assert added.day_of_month == 1
        assert added.include_charts is True
        assert added.include_recommendations is True
        assert added.date_range_days == 30
        assert len(added.recipients) == 2

    def test_create_schedule_sets_next_run(self, service, mock_db):
        """Test that create_schedule calculates next_run_at"""
        schedule = service.create_schedule(
            user_id=uuid.uuid4(),
            name="Test Report",
            frequency=ReportFrequency.DAILY.value,
            report_type=ReportType.DMARC_SUMMARY.value,
            recipients=["test@example.com"],
            hour=10,
        )

        added = mock_db.add.call_args[0][0]
        assert added.next_run_at is not None
        assert added.next_run_at.hour == 10

    def test_create_schedule_with_custom_email(self, service, mock_db):
        """Test creating a schedule with custom email subject and body"""
        schedule = service.create_schedule(
            user_id=uuid.uuid4(),
            name="Custom Report",
            frequency=ReportFrequency.DAILY.value,
            report_type=ReportType.COMPLIANCE_REPORT.value,
            recipients=["compliance@example.com"],
            email_subject="Custom Subject",
            email_body="Custom body text",
            description="A custom report description",
        )

        added = mock_db.add.call_args[0][0]
        assert added.email_subject == "Custom Subject"
        assert added.email_body == "Custom body text"
        assert added.description == "A custom report description"


@pytest.mark.unit
class TestUpdateAndDeleteSchedule:
    """Test updating and deleting scheduled reports"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return ScheduledReportsService(mock_db)

    def test_update_schedule_success(self, service, mock_db):
        """Test updating an existing schedule"""
        schedule_id = uuid.uuid4()
        user_id = uuid.uuid4()

        existing_schedule = Mock(spec=ScheduledReport)
        existing_schedule.id = schedule_id
        existing_schedule.user_id = user_id
        existing_schedule.frequency = "daily"
        existing_schedule.day_of_week = None
        existing_schedule.day_of_month = None
        existing_schedule.hour = 8
        existing_schedule.name = "Old Name"

        mock_db.query.return_value.filter.return_value.first.return_value = existing_schedule

        result = service.update_schedule(
            schedule_id=schedule_id,
            user_id=user_id,
            name="Updated Name",
        )

        assert result is not None
        assert mock_db.commit.called

    def test_update_schedule_not_found(self, service, mock_db):
        """Test updating a nonexistent schedule returns None"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.update_schedule(
            schedule_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            name="Updated",
        )

        assert result is None

    def test_update_schedule_recalculates_next_run(self, service, mock_db):
        """Test that updating frequency recalculates next_run_at"""
        schedule_id = uuid.uuid4()
        user_id = uuid.uuid4()

        existing_schedule = Mock(spec=ScheduledReport)
        existing_schedule.id = schedule_id
        existing_schedule.user_id = user_id
        existing_schedule.frequency = "weekly"
        existing_schedule.day_of_week = 1
        existing_schedule.day_of_month = None
        existing_schedule.hour = 9

        mock_db.query.return_value.filter.return_value.first.return_value = existing_schedule

        result = service.update_schedule(
            schedule_id=schedule_id,
            user_id=user_id,
            frequency="weekly",
        )

        # next_run_at should be recalculated because frequency is in the updates
        assert existing_schedule.next_run_at is not None

    def test_delete_schedule_success(self, service, mock_db):
        """Test deleting an existing schedule"""
        schedule_id = uuid.uuid4()
        user_id = uuid.uuid4()

        existing = Mock(spec=ScheduledReport)
        existing.id = schedule_id
        mock_db.query.return_value.filter.return_value.first.return_value = existing

        result = service.delete_schedule(schedule_id, user_id)

        assert result is True
        assert mock_db.delete.called
        assert mock_db.commit.called

    def test_delete_schedule_not_found(self, service, mock_db):
        """Test deleting a nonexistent schedule returns False"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.delete_schedule(uuid.uuid4(), uuid.uuid4())

        assert result is False
        assert not mock_db.delete.called


@pytest.mark.unit
class TestGetSchedules:
    """Test retrieving schedules"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return ScheduledReportsService(mock_db)

    def test_get_schedules_active_only(self, service, mock_db):
        """Test getting only active schedules"""
        mock_schedules = [Mock(spec=ScheduledReport), Mock(spec=ScheduledReport)]
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = mock_schedules

        user_id = uuid.uuid4()
        result = service.get_schedules(user_id=user_id, active_only=True)

        assert mock_db.query.called

    def test_get_schedule_by_id(self, service, mock_db):
        """Test getting a single schedule by ID"""
        schedule_id = uuid.uuid4()
        expected = Mock(spec=ScheduledReport)
        expected.id = schedule_id
        mock_db.query.return_value.filter.return_value.first.return_value = expected

        result = service.get_schedule(schedule_id)

        assert result is expected

    def test_get_schedule_not_found(self, service, mock_db):
        """Test getting a nonexistent schedule returns None"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.get_schedule(uuid.uuid4())

        assert result is None

    def test_get_due_schedules(self, service, mock_db):
        """Test getting schedules that are due to run"""
        due_schedule = Mock(spec=ScheduledReport)
        due_schedule.next_run_at = datetime.utcnow() - timedelta(minutes=5)
        mock_db.query.return_value.filter.return_value.all.return_value = [due_schedule]

        result = service.get_due_schedules()

        assert len(result) == 1


@pytest.mark.unit
class TestRunSchedule:
    """Test running scheduled reports"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return ScheduledReportsService(mock_db)

    @patch("app.services.scheduled_reports_service.ScheduledReportsService._send_email")
    @patch("app.services.scheduled_reports_service.ScheduledReportsService._generate_report_data")
    def test_run_schedule_success(self, mock_generate, mock_send_email, service, mock_db):
        """Test successful report execution"""
        schedule = Mock(spec=ScheduledReport)
        schedule.id = uuid.uuid4()
        schedule.name = "Test Report"
        schedule.report_type = ReportType.DMARC_SUMMARY.value
        schedule.date_range_days = 7
        schedule.domains = ["example.com"]
        schedule.recipients = ["admin@example.com"]
        schedule.email_subject = "Test Subject"
        schedule.email_body = "Test Body"
        schedule.include_charts = True
        schedule.frequency = "daily"
        schedule.day_of_week = None
        schedule.day_of_month = None
        schedule.hour = 8
        schedule.run_count = 0
        schedule.failure_count = 0

        mock_generate.return_value = {"summary": {"total_reports": 5}}

        with patch("app.services.export_service.ExportService") as MockExport:
            mock_export_instance = MockExport.return_value
            mock_export_instance.generate_pdf_report.return_value = b"fake-pdf-bytes"

            log = service.run_schedule(schedule)

        assert mock_db.add.called
        assert mock_db.commit.called
        assert mock_send_email.called
        assert schedule.run_count == 1

    @patch("app.services.scheduled_reports_service.ScheduledReportsService._generate_report_data")
    def test_run_schedule_failure(self, mock_generate, service, mock_db):
        """Test report execution handles errors gracefully"""
        schedule = Mock(spec=ScheduledReport)
        schedule.id = uuid.uuid4()
        schedule.name = "Test Report"
        schedule.report_type = ReportType.DMARC_SUMMARY.value
        schedule.date_range_days = 7
        schedule.domains = ["example.com"]
        schedule.recipients = ["admin@example.com"]
        schedule.email_subject = None
        schedule.email_body = None
        schedule.include_charts = True
        schedule.frequency = "daily"
        schedule.day_of_week = None
        schedule.day_of_month = None
        schedule.hour = 8
        schedule.run_count = 0
        schedule.failure_count = 0

        mock_generate.side_effect = Exception("Report generation failed")

        with patch("app.services.export_service.ExportService"):
            log = service.run_schedule(schedule)

        # Failure count should increment
        assert schedule.failure_count == 1
        assert mock_db.commit.called

    def test_run_now_success(self, service, mock_db):
        """Test run_now finds the schedule and runs it"""
        schedule_id = uuid.uuid4()
        user_id = uuid.uuid4()

        schedule = Mock(spec=ScheduledReport)
        schedule.id = schedule_id
        schedule.user_id = user_id
        mock_db.query.return_value.filter.return_value.first.return_value = schedule

        with patch.object(service, 'run_schedule', return_value=Mock(spec=ReportDeliveryLog)) as mock_run:
            result = service.run_now(schedule_id, user_id)

        mock_run.assert_called_once_with(schedule)

    def test_run_now_not_found(self, service, mock_db):
        """Test run_now returns None when schedule not found"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.run_now(uuid.uuid4(), uuid.uuid4())

        assert result is None


@pytest.mark.unit
class TestCalculateNextRun:
    """Test next run time calculation"""

    @pytest.fixture
    def service(self):
        return ScheduledReportsService(MagicMock())

    def test_daily_next_run(self, service):
        """Test daily next run calculation"""
        result = service._calculate_next_run("daily", None, None, 10)

        assert result.hour == 10
        assert result.minute == 0
        assert result.second == 0
        # Next run should be in the future
        assert result >= datetime.utcnow().replace(hour=10, minute=0, second=0, microsecond=0)

    def test_weekly_next_run(self, service):
        """Test weekly next run calculation"""
        result = service._calculate_next_run("weekly", 0, None, 8)  # Monday at 8am

        assert result.hour == 8
        assert result.weekday() == 0  # Monday
        assert result > datetime.utcnow()

    def test_monthly_next_run(self, service):
        """Test monthly next run calculation"""
        result = service._calculate_next_run("monthly", None, 15, 9)

        assert result.hour == 9
        assert result.day == 15
        # Should be a future date
        assert result >= datetime.utcnow().replace(minute=0, second=0, microsecond=0)

    def test_monthly_next_run_safe_day(self, service):
        """Test monthly clamps day to 28 for safety"""
        result = service._calculate_next_run("monthly", None, 31, 9)

        # Day should be clamped to 28
        assert result.day == 28


@pytest.mark.unit
class TestEmailAndReportData:
    """Test email generation and report data helpers"""

    @pytest.fixture
    def service(self):
        return ScheduledReportsService(MagicMock())

    def test_default_email_body(self, service):
        """Test default email body generation"""
        schedule = Mock(spec=ScheduledReport)
        schedule.report_type = "dmarc_summary"
        schedule.name = "Weekly DMARC"
        schedule.frequency = "weekly"
        schedule.date_range_days = 7
        schedule.domains = ["example.com", "test.com"]

        body = service._default_email_body(schedule)

        assert "Weekly DMARC" in body
        assert "Weekly" in body
        assert "7 days" in body
        assert "example.com" in body
        assert "DMARC Dashboard" in body

    def test_default_email_body_all_domains(self, service):
        """Test default email body when domains is None (all domains)"""
        schedule = Mock(spec=ScheduledReport)
        schedule.report_type = "threat_report"
        schedule.name = "Threat Report"
        schedule.frequency = "daily"
        schedule.date_range_days = 1
        schedule.domains = None

        body = service._default_email_body(schedule)

        assert "All domains" in body

    @patch("app.services.scheduled_reports_service.settings")
    def test_send_email_no_smtp_configured(self, mock_settings, service):
        """Test send_email gracefully handles missing SMTP configuration"""
        mock_settings.smtp_host = None
        mock_settings.smtp_from = "noreply@example.com"

        # Should not raise, just log a warning
        service._send_email(
            recipients=["test@example.com"],
            subject="Test",
            body="Test body",
            attachment=b"fake-pdf",
            attachment_name="report.pdf",
        )

    @patch("app.services.scheduled_reports_service.settings")
    @patch("app.services.scheduled_reports_service.smtplib.SMTP")
    def test_send_email_with_smtp(self, mock_smtp_class, mock_settings, service):
        """Test send_email connects and sends via SMTP"""
        mock_settings.smtp_host = "smtp.example.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_username = "user"
        mock_settings.smtp_password = "pass"
        mock_settings.smtp_from = "noreply@example.com"

        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__ = Mock(return_value=mock_smtp)
        mock_smtp_class.return_value.__exit__ = Mock(return_value=False)

        service._send_email(
            recipients=["test@example.com"],
            subject="Test Report",
            body="Report body",
            attachment=b"fake-pdf-content",
            attachment_name="report_20240101.pdf",
        )

        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("user", "pass")
        mock_smtp.sendmail.assert_called_once()


@pytest.mark.unit
class TestGetDeliveryLogs:
    """Test delivery log retrieval"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return ScheduledReportsService(mock_db)

    def test_get_delivery_logs_default(self, service, mock_db):
        """Test getting delivery logs with defaults"""
        mock_logs = [Mock(spec=ReportDeliveryLog)]
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_logs

        result = service.get_delivery_logs()

        assert mock_db.query.called

    def test_get_delivery_logs_filtered(self, service, mock_db):
        """Test getting delivery logs filtered by schedule and status"""
        mock_logs = []
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_logs

        schedule_id = uuid.uuid4()
        result = service.get_delivery_logs(
            schedule_id=schedule_id,
            status=DeliveryStatus.DELIVERED.value,
            days=7,
            limit=10,
        )

        assert mock_db.query.called
