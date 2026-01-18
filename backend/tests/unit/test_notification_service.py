"""Unit tests for notification service"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import uuid

from app.services.notification_service import NotificationService
from app.models.notification import UserNotification, NotificationType, NotificationPriority


class TestNotificationCreation:
    """Test notification creation"""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        return db

    @pytest.fixture
    def user_id(self):
        """Create test user ID"""
        return uuid.uuid4()

    def test_create_notification_basic(self, mock_db, user_id):
        """Test basic notification creation"""
        notification = NotificationService.create_notification(
            db=mock_db,
            user_id=user_id,
            title="Test Notification",
            message="This is a test message",
            notification_type=NotificationType.INFO
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_notification_with_priority(self, mock_db, user_id):
        """Test notification creation with priority"""
        notification = NotificationService.create_notification(
            db=mock_db,
            user_id=user_id,
            title="High Priority",
            message="Urgent message",
            notification_type=NotificationType.ALERT,
            priority=NotificationPriority.HIGH
        )

        mock_db.add.assert_called_once()

    def test_create_notification_with_link(self, mock_db, user_id):
        """Test notification creation with action link"""
        notification = NotificationService.create_notification(
            db=mock_db,
            user_id=user_id,
            title="Report Ready",
            message="Your report is ready",
            notification_type=NotificationType.REPORT,
            action_url="/reports/123"
        )

        mock_db.add.assert_called_once()

    def test_create_notification_with_expiration(self, mock_db, user_id):
        """Test notification creation with expiration"""
        expires_at = datetime.utcnow() + timedelta(days=7)

        notification = NotificationService.create_notification(
            db=mock_db,
            user_id=user_id,
            title="Expiring Notice",
            message="This will expire",
            notification_type=NotificationType.INFO,
            expires_at=expires_at
        )

        mock_db.add.assert_called_once()


class TestNotificationRetrieval:
    """Test notification retrieval"""

    @pytest.fixture
    def mock_notifications(self):
        """Create mock notifications"""
        notifications = []
        for i in range(5):
            n = Mock(spec=UserNotification)
            n.id = uuid.uuid4()
            n.title = f"Notification {i}"
            n.message = f"Message {i}"
            n.is_read = i < 2  # First 2 are read
            n.created_at = datetime.utcnow() - timedelta(hours=i)
            notifications.append(n)
        return notifications

    def test_get_user_notifications(self, mock_notifications):
        """Test getting user notifications"""
        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_notifications
        mock_db.query.return_value = mock_query

        user_id = uuid.uuid4()
        result = NotificationService.get_user_notifications(
            db=mock_db,
            user_id=user_id,
            skip=0,
            limit=10
        )

        assert len(result) == 5
        mock_db.query.assert_called()

    def test_get_unread_notifications(self, mock_notifications):
        """Test getting only unread notifications"""
        unread = [n for n in mock_notifications if not n.is_read]

        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = unread
        mock_db.query.return_value = mock_query

        user_id = uuid.uuid4()
        result = NotificationService.get_unread_notifications(
            db=mock_db,
            user_id=user_id
        )

        assert len(result) == 3


class TestNotificationActions:
    """Test notification actions"""

    @pytest.fixture
    def mock_notification(self):
        """Create mock notification"""
        n = Mock(spec=UserNotification)
        n.id = uuid.uuid4()
        n.user_id = uuid.uuid4()
        n.is_read = False
        n.read_at = None
        return n

    def test_mark_as_read(self, mock_notification):
        """Test marking notification as read"""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_notification

        result = NotificationService.mark_as_read(
            db=mock_db,
            notification_id=mock_notification.id,
            user_id=mock_notification.user_id
        )

        assert mock_notification.is_read is True
        assert mock_notification.read_at is not None
        mock_db.commit.assert_called()

    def test_mark_as_read_not_found(self):
        """Test marking non-existent notification"""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = NotificationService.mark_as_read(
            db=mock_db,
            notification_id=uuid.uuid4(),
            user_id=uuid.uuid4()
        )

        assert result is None

    def test_mark_all_as_read(self):
        """Test marking all notifications as read"""
        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 5
        mock_db.query.return_value = mock_query

        user_id = uuid.uuid4()
        count = NotificationService.mark_all_as_read(
            db=mock_db,
            user_id=user_id
        )

        mock_db.commit.assert_called()

    def test_delete_notification(self, mock_notification):
        """Test deleting notification"""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_notification

        result = NotificationService.delete_notification(
            db=mock_db,
            notification_id=mock_notification.id,
            user_id=mock_notification.user_id
        )

        assert result is True
        mock_db.delete.assert_called_with(mock_notification)
        mock_db.commit.assert_called()

    def test_delete_notification_not_found(self):
        """Test deleting non-existent notification"""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = NotificationService.delete_notification(
            db=mock_db,
            notification_id=uuid.uuid4(),
            user_id=uuid.uuid4()
        )

        assert result is False


class TestNotificationCounts:
    """Test notification count methods"""

    def test_get_unread_count(self):
        """Test getting unread notification count"""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.count.return_value = 5

        user_id = uuid.uuid4()
        count = NotificationService.get_unread_count(
            db=mock_db,
            user_id=user_id
        )

        assert count == 5

    def test_get_notification_counts(self):
        """Test getting all notification counts"""
        mock_db = Mock()

        # Mock total count
        mock_db.query.return_value.filter.return_value.count.side_effect = [10, 3]

        user_id = uuid.uuid4()
        counts = NotificationService.get_notification_counts(
            db=mock_db,
            user_id=user_id
        )

        assert counts["total"] == 10
        assert counts["unread"] == 3


class TestBroadcastNotifications:
    """Test broadcast notification functionality"""

    def test_broadcast_to_all_users(self):
        """Test broadcasting notification to all users"""
        mock_db = Mock()

        # Mock user query
        mock_users = [Mock(id=uuid.uuid4()) for _ in range(3)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_users

        count = NotificationService.broadcast_notification(
            db=mock_db,
            title="System Announcement",
            message="System will be down for maintenance",
            notification_type=NotificationType.SYSTEM
        )

        # Should add notification for each user
        assert mock_db.add.call_count == 3
        mock_db.commit.assert_called()


class TestCleanupExpiredNotifications:
    """Test cleanup of expired notifications"""

    def test_cleanup_expired(self):
        """Test cleaning up expired notifications"""
        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 5
        mock_db.query.return_value = mock_query

        count = NotificationService.cleanup_expired_notifications(db=mock_db)

        mock_db.commit.assert_called()

    def test_cleanup_old_read_notifications(self):
        """Test cleaning up old read notifications"""
        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 10
        mock_db.query.return_value = mock_query

        count = NotificationService.cleanup_old_read_notifications(
            db=mock_db,
            days_old=30
        )

        mock_db.commit.assert_called()
