"""Unit tests for RetentionService (retention_service.py)"""
import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from app.models import RetentionPolicy, RetentionLog, RetentionTarget
from app.services.retention_service import RetentionService, RetentionError


@pytest.mark.unit
class TestPolicyCRUD:
    """Test policy CRUD operations"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return RetentionService(mock_db)

    def test_create_policy(self, service, mock_db):
        """Test creating a new retention policy"""
        mock_db.query.return_value.filter.return_value.first.return_value = None  # no duplicate

        policy = service.create_policy(
            name="Test Policy",
            target=RetentionTarget.DMARC_REPORTS,
            retention_days=365,
            description="Keep reports for 1 year",
        )

        assert mock_db.add.called
        assert mock_db.commit.called
        added = mock_db.add.call_args[0][0]
        assert added.name == "Test Policy"
        assert added.target == RetentionTarget.DMARC_REPORTS.value
        assert added.retention_days == 365

    def test_create_duplicate_name_raises(self, service, mock_db):
        """Test creating a policy with duplicate name raises error"""
        existing = Mock()
        existing.name = "Existing Policy"
        mock_db.query.return_value.filter.return_value.first.return_value = existing

        with pytest.raises(RetentionError, match="already exists"):
            service.create_policy(
                name="Existing Policy",
                target=RetentionTarget.AUDIT_LOGS,
                retention_days=90,
            )

    def test_update_policy(self, service, mock_db):
        """Test updating a retention policy"""
        policy = Mock()
        policy.id = uuid.uuid4()
        policy.name = "Old Name"
        policy.retention_days = 90
        mock_db.query.return_value.filter.return_value.first.return_value = policy

        result = service.update_policy(
            policy_id=policy.id,
            name="New Name",
            retention_days=180,
        )

        assert result.name == "New Name"
        assert result.retention_days == 180
        assert mock_db.commit.called

    def test_update_nonexistent_policy_raises(self, service, mock_db):
        """Test updating a nonexistent policy raises error"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(RetentionError, match="not found"):
            service.update_policy(policy_id=uuid.uuid4(), name="New Name")

    def test_delete_policy(self, service, mock_db):
        """Test deleting a policy"""
        policy = Mock()
        policy.id = uuid.uuid4()
        policy.name = "To Delete"
        mock_db.query.return_value.filter.return_value.first.return_value = policy

        result = service.delete_policy(policy.id)

        assert result is True
        assert mock_db.delete.called
        assert mock_db.commit.called

    def test_delete_nonexistent_policy_raises(self, service, mock_db):
        """Test deleting a nonexistent policy raises error"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(RetentionError, match="not found"):
            service.delete_policy(uuid.uuid4())

    def test_get_policy_by_id(self, service, mock_db):
        """Test getting a policy by ID"""
        policy = Mock()
        policy.id = uuid.uuid4()
        mock_db.query.return_value.filter.return_value.first.return_value = policy

        result = service.get_policy(policy.id)
        assert result == policy

    def test_get_policies_all(self, service, mock_db):
        """Test getting all policies"""
        policies = [Mock(), Mock()]
        mock_db.query.return_value.order_by.return_value.all.return_value = policies

        result = service.get_policies()
        assert len(result) == 2

    def test_get_policies_by_target(self, service, mock_db):
        """Test filtering policies by target"""
        service.get_policies(target="dmarc_reports")
        assert mock_db.query.called

    def test_get_policies_enabled_only(self, service, mock_db):
        """Test filtering policies by enabled status"""
        service.get_policies(is_enabled=True)
        assert mock_db.query.called


@pytest.mark.unit
class TestDataCleanup:
    """Test data cleanup based on age"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return RetentionService(mock_db)

    def test_execute_policy_deletes_old_records(self, service, mock_db):
        """Test policy execution deletes records older than retention period"""
        policy = Mock()
        policy.id = uuid.uuid4()
        policy.name = "Audit Cleanup"
        policy.target = RetentionTarget.AUDIT_LOGS.value
        policy.retention_days = 90
        policy.filters = None
        policy.total_deleted = 0

        # 50 records to delete
        mock_db.query.return_value.filter.return_value.count.return_value = 50
        mock_db.query.return_value.filter.return_value.delete.return_value = 50

        log = service.execute_policy(policy)

        assert mock_db.commit.called
        saved_log = mock_db.add.call_args[0][0]
        assert saved_log.records_deleted == 50
        assert saved_log.success is True
        assert policy.last_run_at is not None

    def test_execute_policy_no_records_to_delete(self, service, mock_db):
        """Test policy execution with no records to delete"""
        policy = Mock()
        policy.id = uuid.uuid4()
        policy.name = "Empty Cleanup"
        policy.target = RetentionTarget.ALERT_HISTORY.value
        policy.retention_days = 180
        policy.filters = None
        policy.total_deleted = 0

        mock_db.query.return_value.filter.return_value.count.return_value = 0

        log = service.execute_policy(policy)

        saved_log = mock_db.add.call_args[0][0]
        assert saved_log.records_deleted == 0
        assert saved_log.success is True

    def test_execute_policy_unknown_target(self, service, mock_db):
        """Test policy execution with unknown target logs error"""
        policy = Mock()
        policy.id = uuid.uuid4()
        policy.name = "Bad Target"
        policy.target = "nonexistent_target"
        policy.retention_days = 30
        policy.filters = None

        log = service.execute_policy(policy)

        saved_log = mock_db.add.call_args[0][0]
        assert saved_log.success is False
        assert "Unknown target" in saved_log.error_message

    def test_execute_policy_handles_exception(self, service, mock_db):
        """Test policy execution handles database errors gracefully"""
        policy = Mock()
        policy.id = uuid.uuid4()
        policy.name = "Error Policy"
        policy.target = RetentionTarget.DMARC_REPORTS.value
        policy.retention_days = 365
        policy.filters = None
        policy.total_deleted = 0

        # Simulate database error during delete
        mock_db.query.return_value.filter.return_value.count.return_value = 10
        mock_db.query.return_value.filter.return_value.delete.side_effect = Exception("DB error")

        log = service.execute_policy(policy)

        assert mock_db.rollback.called
        saved_log = mock_db.add.call_args[0][0]
        assert saved_log.success is False
        assert "DB error" in saved_log.error_message

    def test_execute_all_policies(self, service, mock_db):
        """Test executing all enabled policies"""
        policy1 = Mock()
        policy1.id = uuid.uuid4()
        policy1.name = "Policy 1"
        policy1.target = RetentionTarget.AUDIT_LOGS.value
        policy1.retention_days = 90
        policy1.filters = None
        policy1.total_deleted = 0
        policy1.is_enabled = True

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [policy1]
        mock_db.query.return_value.filter.return_value.count.return_value = 5
        mock_db.query.return_value.filter.return_value.delete.return_value = 5

        logs = service.execute_all_policies()
        assert len(logs) >= 1

    def test_preview_policy(self, service, mock_db):
        """Test previewing what would be deleted"""
        policy = Mock()
        policy.target = RetentionTarget.ANALYTICS_CACHE.value
        policy.retention_days = 30
        policy.filters = None

        mock_db.query.return_value.select_from.return_value.filter.return_value.scalar.return_value = 25

        result = service.preview_policy(policy)

        assert result["target"] == "analytics_cache"
        assert result["records_to_delete"] == 25
        assert result["retention_days"] == 30
