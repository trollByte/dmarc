"""Unit tests for EnhancedAlertService (alerting_v2.py)"""
import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from app.models import AlertHistory, AlertRule, AlertSuppression, AlertSeverity, AlertType, AlertStatus
from app.services.alerting_v2 import EnhancedAlertService


@pytest.mark.unit
class TestAlertCreation:
    """Test alert creation with different types and severities"""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        return db

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.alerting_v2.NotificationService"):
            return EnhancedAlertService(mock_db)

    def test_create_alert_success(self, service, mock_db):
        """Test creating an alert with valid parameters"""
        mock_db.query.return_value.filter.return_value.all.return_value = []  # no suppressions
        mock_db.query.return_value.filter.return_value.first.return_value = None  # no cooldown rule
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None  # no recent alert

        alert = service.create_alert(
            alert_type=AlertType.FAILURE_RATE,
            severity=AlertSeverity.CRITICAL,
            title="High failure rate",
            message="DMARC failure rate is 50%",
            domain="example.com",
            current_value=50.0,
            threshold_value=25.0,
        )

        assert mock_db.add.called
        assert mock_db.commit.called
        added_alert = mock_db.add.call_args[0][0]
        assert added_alert.alert_type == AlertType.FAILURE_RATE
        assert added_alert.severity == AlertSeverity.CRITICAL
        assert added_alert.status == AlertStatus.CREATED
        assert added_alert.domain == "example.com"

    def test_create_alert_warning_severity(self, service, mock_db):
        """Test creating a warning-level alert"""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        service.create_alert(
            alert_type=AlertType.VOLUME_SPIKE,
            severity=AlertSeverity.WARNING,
            title="Volume spike",
            message="Volume increased 200%",
        )

        added_alert = mock_db.add.call_args[0][0]
        assert added_alert.severity == AlertSeverity.WARNING
        assert added_alert.alert_type == AlertType.VOLUME_SPIKE

    def test_create_alert_with_metadata(self, service, mock_db):
        """Test creating an alert with additional metadata"""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        metadata = {"rule_id": "abc-123", "source": "scheduled_check"}
        service.create_alert(
            alert_type=AlertType.ANOMALY,
            severity=AlertSeverity.INFO,
            title="Anomaly detected",
            message="Unusual pattern",
            metadata=metadata,
        )

        added_alert = mock_db.add.call_args[0][0]
        assert added_alert.alert_metadata == metadata


@pytest.mark.unit
class TestAlertDeduplication:
    """Test deduplication via fingerprint matching"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.alerting_v2.NotificationService"):
            return EnhancedAlertService(mock_db)

    def test_fingerprint_generation_deterministic(self, service):
        """Test that same inputs produce same fingerprint"""
        fp1 = service._generate_fingerprint(AlertType.FAILURE_RATE, "example.com", 50.0, 25.0)
        fp2 = service._generate_fingerprint(AlertType.FAILURE_RATE, "example.com", 75.0, 25.0)
        # Fingerprint uses threshold, not current value - so same threshold = same fingerprint
        assert fp1 == fp2

    def test_fingerprint_different_for_different_types(self, service):
        """Test different alert types produce different fingerprints"""
        fp1 = service._generate_fingerprint(AlertType.FAILURE_RATE, "example.com", 50.0, 25.0)
        fp2 = service._generate_fingerprint(AlertType.VOLUME_SPIKE, "example.com", 50.0, 25.0)
        assert fp1 != fp2

    def test_fingerprint_different_for_different_domains(self, service):
        """Test different domains produce different fingerprints"""
        fp1 = service._generate_fingerprint(AlertType.FAILURE_RATE, "example.com", 50.0, 25.0)
        fp2 = service._generate_fingerprint(AlertType.FAILURE_RATE, "other.com", 50.0, 25.0)
        assert fp1 != fp2

    def test_deduplicated_alert_returns_none(self, service, mock_db):
        """Test that a duplicate alert within cooldown returns None"""
        # Simulate existing recent alert with matching fingerprint
        existing_alert = Mock()
        existing_alert.id = uuid.uuid4()
        existing_alert.cooldown_until = datetime.utcnow() + timedelta(hours=1)

        # No suppressions
        mock_db.query.return_value.filter.return_value.all.return_value = []
        # No cooldown rule
        mock_db.query.return_value.filter.return_value.first.return_value = None
        # Existing alert found in recent alerts
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = existing_alert

        result = service.create_alert(
            alert_type=AlertType.FAILURE_RATE,
            severity=AlertSeverity.CRITICAL,
            title="High failure rate",
            message="Same alert",
            domain="example.com",
        )

        assert result is None

    def test_force_skips_deduplication(self, service, mock_db):
        """Test that force=True skips deduplication"""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service.create_alert(
            alert_type=AlertType.FAILURE_RATE,
            severity=AlertSeverity.CRITICAL,
            title="Forced alert",
            message="Forced",
            force=True,
        )

        assert mock_db.add.called


@pytest.mark.unit
class TestAlertCooldown:
    """Test cooldown period enforcement"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.alerting_v2.NotificationService"):
            return EnhancedAlertService(mock_db)

    def test_default_cooldown_failure_rate(self, service, mock_db):
        """Test default cooldown for failure_rate is 60 minutes"""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = service._get_cooldown_minutes(AlertType.FAILURE_RATE)
        assert result == 60

    def test_default_cooldown_volume_spike(self, service, mock_db):
        """Test default cooldown for volume_spike is 120 minutes"""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = service._get_cooldown_minutes(AlertType.VOLUME_SPIKE)
        assert result == 120

    def test_rule_overrides_default_cooldown(self, service, mock_db):
        """Test that a rule's cooldown overrides the default"""
        mock_rule = Mock()
        mock_rule.cooldown_minutes = 30
        mock_rule.is_enabled = True
        mock_db.query.return_value.filter.return_value.first.return_value = mock_rule

        result = service._get_cooldown_minutes(AlertType.FAILURE_RATE)
        assert result == 30


@pytest.mark.unit
class TestAlertLifecycle:
    """Test alert acknowledge/resolve lifecycle"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.alerting_v2.NotificationService"):
            return EnhancedAlertService(mock_db)

    def test_acknowledge_alert(self, service, mock_db):
        """Test acknowledging a created alert"""
        alert = Mock()
        alert.id = uuid.uuid4()
        alert.status = AlertStatus.CREATED
        alert.alert_type = Mock(value="failure_rate")
        mock_db.query.return_value.filter.return_value.first.return_value = alert

        result = service.acknowledge_alert(str(alert.id), "user-123", note="Investigating")

        assert result.status == AlertStatus.ACKNOWLEDGED
        assert result.acknowledged_by == "user-123"
        assert result.acknowledgement_note == "Investigating"
        assert mock_db.commit.called

    def test_acknowledge_already_acknowledged_raises(self, service, mock_db):
        """Test acknowledging an already acknowledged alert raises ValueError"""
        alert = Mock()
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.alert_type = Mock(value="failure_rate")
        mock_db.query.return_value.filter.return_value.first.return_value = alert

        with pytest.raises(ValueError, match="already"):
            service.acknowledge_alert("alert-id", "user-123")

    def test_acknowledge_nonexistent_alert_raises(self, service, mock_db):
        """Test acknowledging a nonexistent alert raises ValueError"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="not found"):
            service.acknowledge_alert("nonexistent-id", "user-123")

    def test_resolve_alert(self, service, mock_db):
        """Test resolving an alert"""
        alert = Mock()
        alert.id = uuid.uuid4()
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.alert_type = Mock(value="failure_rate")
        mock_db.query.return_value.filter.return_value.first.return_value = alert

        result = service.resolve_alert(str(alert.id), "user-456", note="Fixed the issue")

        assert result.status == AlertStatus.RESOLVED
        assert result.resolved_by == "user-456"
        assert result.resolution_note == "Fixed the issue"

    def test_resolve_already_resolved_raises(self, service, mock_db):
        """Test resolving an already resolved alert raises ValueError"""
        alert = Mock()
        alert.status = AlertStatus.RESOLVED
        mock_db.query.return_value.filter.return_value.first.return_value = alert

        with pytest.raises(ValueError, match="already resolved"):
            service.resolve_alert("alert-id", "user-123")

    def test_resolve_nonexistent_alert_raises(self, service, mock_db):
        """Test resolving a nonexistent alert raises ValueError"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="not found"):
            service.resolve_alert("nonexistent-id", "user-123")

    def test_resolve_from_created_status(self, service, mock_db):
        """Test resolving an alert directly from created status"""
        alert = Mock()
        alert.id = uuid.uuid4()
        alert.status = AlertStatus.CREATED
        alert.alert_type = Mock(value="failure_rate")
        mock_db.query.return_value.filter.return_value.first.return_value = alert

        result = service.resolve_alert(str(alert.id), "user-789")

        assert result.status == AlertStatus.RESOLVED
