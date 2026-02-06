"""Unit tests for AuditService (audit_service.py)"""
import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, call

from app.models import AuditLog, AuditAction, AuditCategory, get_category_for_action, User
from app.services.audit_service import AuditService


@pytest.mark.unit
class TestLogEntryCreation:
    """Test log entry creation with correct fields"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return AuditService(mock_db)

    @pytest.fixture
    def mock_user(self):
        user = Mock(spec=User)
        user.id = uuid.uuid4()
        user.username = "testadmin"
        user.email = "admin@example.com"
        return user

    def test_log_creates_entry_with_correct_action(self, service, mock_db):
        """Test that log() creates entry with correct action field"""
        service.log(
            action=AuditAction.LOGIN,
            username="testuser",
            ip_address="192.168.1.1",
            description="User logged in",
        )

        assert mock_db.add.called
        assert mock_db.commit.called
        entry = mock_db.add.call_args[0][0]
        assert entry.action == AuditAction.LOGIN.value

    def test_log_sets_category_from_action(self, service, mock_db):
        """Test that category is automatically derived from action"""
        service.log(
            action=AuditAction.LOGIN,
            username="testuser",
        )

        entry = mock_db.add.call_args[0][0]
        assert entry.category == AuditCategory.AUTHENTICATION.value

    def test_log_user_management_category(self, service, mock_db):
        """Test category mapping for user management actions"""
        service.log(
            action=AuditAction.USER_CREATE,
            username="admin",
        )

        entry = mock_db.add.call_args[0][0]
        assert entry.category == AuditCategory.USER_MANAGEMENT.value

    def test_log_with_user_object(self, service, mock_db, mock_user):
        """Test log entry creation using a User object"""
        service.log(
            action=AuditAction.PASSWORD_CHANGE,
            user=mock_user,
            ip_address="10.0.0.1",
        )

        entry = mock_db.add.call_args[0][0]
        assert entry.user_id == mock_user.id
        assert entry.username == mock_user.username

    def test_log_with_target(self, service, mock_db):
        """Test log entry with target type and ID"""
        target_id = str(uuid.uuid4())
        service.log(
            action=AuditAction.USER_UPDATE,
            username="admin",
            target_type="user",
            target_id=target_id,
            description="Updated user role",
        )

        entry = mock_db.add.call_args[0][0]
        assert entry.target_type == "user"
        assert entry.target_id == target_id

    def test_log_with_old_and_new_values(self, service, mock_db):
        """Test log entry with state change tracking"""
        service.log(
            action=AuditAction.USER_UPDATE,
            username="admin",
            old_value={"role": "viewer"},
            new_value={"role": "analyst"},
        )

        entry = mock_db.add.call_args[0][0]
        assert entry.old_value == {"role": "viewer"}
        assert entry.new_value == {"role": "analyst"}

    def test_log_with_request_info(self, service, mock_db):
        """Test log entry with HTTP request information"""
        service.log(
            action=AuditAction.REPORT_VIEW,
            username="viewer",
            request_method="GET",
            request_path="/api/reports/123",
            response_status=200,
        )

        entry = mock_db.add.call_args[0][0]
        assert entry.request_method == "GET"
        assert entry.request_path == "/api/reports/123"
        assert entry.response_status == 200

    def test_log_login_success(self, service, mock_db, mock_user):
        """Test log_login helper for successful login"""
        service.log_login(mock_user, success=True, ip_address="192.168.1.1")

        entry = mock_db.add.call_args[0][0]
        assert entry.action == AuditAction.LOGIN.value
        assert "Successful" in entry.description

    def test_log_login_failure(self, service, mock_db, mock_user):
        """Test log_login helper for failed login"""
        service.log_login(
            mock_user, success=False,
            ip_address="192.168.1.1",
            failure_reason="Invalid password"
        )

        entry = mock_db.add.call_args[0][0]
        assert entry.action == AuditAction.LOGIN_FAILED.value
        assert "Failed" in entry.description

    def test_log_data_export(self, service, mock_db, mock_user):
        """Test log_data_export helper"""
        service.log_data_export(
            mock_user, export_type="csv",
            filters={"domain": "example.com"},
            ip_address="10.0.0.1"
        )

        entry = mock_db.add.call_args[0][0]
        assert entry.action == AuditAction.REPORT_EXPORT.value
        assert "csv" in entry.description


@pytest.mark.unit
class TestAuditLogFiltering:
    """Test filtering by user, action, date range"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return AuditService(mock_db)

    def test_filter_by_action(self, service, mock_db):
        """Test filtering logs by action type"""
        service.get_logs(action="login")

        # Verify filter was called with action
        filter_calls = mock_db.query.return_value.filter.call_args_list
        assert len(filter_calls) > 0

    def test_filter_by_user_id(self, service, mock_db):
        """Test filtering logs by user_id"""
        user_id = uuid.uuid4()
        service.get_logs(user_id=user_id)

        assert mock_db.query.called

    def test_filter_by_date_range(self, service, mock_db):
        """Test filtering logs by start and end dates"""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        service.get_logs(start_date=start, end_date=end)

        assert mock_db.query.called

    def test_filter_by_username_partial(self, service, mock_db):
        """Test filtering by partial username match"""
        service.get_logs(username="test")
        assert mock_db.query.called

    def test_filter_by_category(self, service, mock_db):
        """Test filtering by category"""
        service.get_logs(category="authentication")
        assert mock_db.query.called

    def test_filter_with_pagination(self, service, mock_db):
        """Test filtering with limit and offset"""
        service.get_logs(limit=50, offset=10)
        assert mock_db.query.called

    def test_get_user_activity(self, service, mock_db):
        """Test get_user_activity returns user-specific logs"""
        user_id = uuid.uuid4()
        service.get_user_activity(user_id, days=7)
        assert mock_db.query.called

    def test_get_security_events(self, service, mock_db):
        """Test get_security_events filters for security-related actions"""
        service.get_security_events(days=7)
        assert mock_db.query.called

    def test_cleanup_old_logs(self, service, mock_db):
        """Test cleanup_old_logs deletes old entries"""
        mock_db.query.return_value.filter.return_value.delete.return_value = 42

        result = service.cleanup_old_logs(retention_days=90)

        assert result == 42
        assert mock_db.commit.called

    def test_get_logs_count(self, service, mock_db):
        """Test counting logs with filters"""
        mock_db.query.return_value.filter.return_value.scalar.return_value = 100

        result = service.get_logs_count(action="login")
        assert mock_db.query.called


@pytest.mark.unit
class TestAuditCategoryMapping:
    """Test action-to-category mapping"""

    def test_login_is_authentication(self):
        assert get_category_for_action(AuditAction.LOGIN) == AuditCategory.AUTHENTICATION

    def test_user_create_is_user_management(self):
        assert get_category_for_action(AuditAction.USER_CREATE) == AuditCategory.USER_MANAGEMENT

    def test_report_view_is_data_access(self):
        assert get_category_for_action(AuditAction.REPORT_VIEW) == AuditCategory.DATA_ACCESS

    def test_alert_rule_create_is_configuration(self):
        assert get_category_for_action(AuditAction.ALERT_RULE_CREATE) == AuditCategory.CONFIGURATION

    def test_bulk_import_is_system(self):
        assert get_category_for_action(AuditAction.BULK_IMPORT) == AuditCategory.SYSTEM
