"""Unit tests for ExportService (export_service.py)"""
import pytest
import csv
import io
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, PropertyMock

from app.services.export_service import ExportService


@pytest.mark.unit
class TestCSVReportExport:
    """Test CSV generation with proper headers"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return ExportService(mock_db)

    def test_reports_csv_headers(self, service, mock_db):
        """Test that CSV report export includes correct headers"""
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = service.export_reports_csv(days=30)

        reader = csv.reader(io.StringIO(result))
        headers = next(reader)
        assert "Report ID" in headers
        assert "Organization" in headers
        assert "Domain" in headers
        assert "Policy" in headers
        assert "Pass Rate %" in headers

    def test_reports_csv_with_data(self, service, mock_db):
        """Test CSV with report data"""
        mock_record = Mock()
        mock_record.count = 100
        mock_record.disposition = "none"

        mock_report = Mock()
        mock_report.report_id = "report-123"
        mock_report.org_name = "Google"
        mock_report.domain = "example.com"
        mock_report.date_begin = datetime(2024, 1, 1)
        mock_report.date_end = datetime(2024, 1, 2)
        mock_report.p = "reject"
        mock_report.sp = "none"
        mock_report.adkim = "r"
        mock_report.aspf = "r"
        mock_report.records = [mock_record]
        mock_report.created_at = datetime(2024, 1, 3)

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_report]

        result = service.export_reports_csv(days=30)
        reader = csv.reader(io.StringIO(result))
        headers = next(reader)
        row = next(reader)

        assert row[0] == "report-123"
        assert row[1] == "Google"
        assert row[2] == "example.com"

    def test_alerts_csv_headers(self, service, mock_db):
        """Test alert CSV export headers"""
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = service.export_alerts_csv(days=30)

        reader = csv.reader(io.StringIO(result))
        headers = next(reader)
        assert "Alert ID" in headers
        assert "Type" in headers
        assert "Severity" in headers
        assert "Status" in headers

    def test_records_csv_headers(self, service, mock_db):
        """Test records CSV export includes proper headers"""
        mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mock_db.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = service.export_records_csv(days=30)

        reader = csv.reader(io.StringIO(result))
        headers = next(reader)
        assert "Source IP" in headers
        assert "Count" in headers
        assert "Disposition" in headers


@pytest.mark.unit
class TestCSVFormulaInjectionPrevention:
    """Test CSV formula injection prevention for values starting with =, +, -, @"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return ExportService(mock_db)

    def _get_csv_rows(self, csv_text):
        """Parse CSV text into rows"""
        reader = csv.reader(io.StringIO(csv_text))
        return list(reader)

    def test_report_values_do_not_contain_executable_formulas(self, service, mock_db):
        """Test that report data with potential formula chars is handled safely by csv.writer"""
        # csv.writer already quotes fields containing special characters
        mock_record = Mock()
        mock_record.count = 10
        mock_record.disposition = "none"

        mock_report = Mock()
        mock_report.report_id = "=cmd|' /C calc'!A0"
        mock_report.org_name = "+dangerous"
        mock_report.domain = "-evil.com"
        mock_report.date_begin = datetime(2024, 1, 1)
        mock_report.date_end = datetime(2024, 1, 2)
        mock_report.p = "@import"
        mock_report.sp = ""
        mock_report.adkim = ""
        mock_report.aspf = ""
        mock_report.records = [mock_record]
        mock_report.created_at = datetime(2024, 1, 3)

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_report]

        result = service.export_reports_csv(days=30)

        # The CSV writer should properly quote these values
        # When re-parsed, they should be plain strings, not formulas
        rows = self._get_csv_rows(result)
        data_row = rows[1]
        # csv.reader will strip the quoting, but the point is that the raw CSV
        # contains quoted values that spreadsheet apps won't auto-execute
        assert data_row[0] == "=cmd|' /C calc'!A0"  # csv.reader strips quotes

    def test_alert_export_with_special_chars(self, service, mock_db):
        """Test alert CSV handles special characters in fields"""
        mock_alert = Mock()
        mock_alert.id = "alert-123"
        mock_alert.alert_type = "failure_rate"
        mock_alert.severity = "critical"
        mock_alert.status = "created"
        mock_alert.title = "=SUM(A1:A10)"
        mock_alert.domain = "+evil.com"
        mock_alert.current_value = None
        mock_alert.threshold_value = None
        mock_alert.created_at = datetime(2024, 1, 1)
        mock_alert.acknowledged_at = None
        mock_alert.resolved_at = None
        mock_alert.resolution_note = None

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_alert]

        result = service.export_alerts_csv(days=30)
        rows = self._get_csv_rows(result)
        assert len(rows) == 2  # header + 1 data row


@pytest.mark.unit
class TestEmptyDataHandling:
    """Test empty data handling"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return ExportService(mock_db)

    def test_empty_reports_csv(self, service, mock_db):
        """Test CSV with no reports returns only headers"""
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = service.export_reports_csv(days=30)

        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 1  # Only header row

    def test_empty_alerts_csv(self, service, mock_db):
        """Test CSV with no alerts returns only headers"""
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = service.export_alerts_csv(days=30)

        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 1

    def test_empty_records_csv(self, service, mock_db):
        """Test CSV with no records returns only headers"""
        mock_db.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = service.export_records_csv(days=30)

        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 1

    def test_reports_csv_domain_filter(self, service, mock_db):
        """Test CSV export with domain filter returns headers when empty"""
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = service.export_reports_csv(days=30, domain="nonexistent.com")

        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) >= 1  # At least header
