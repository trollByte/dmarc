"""Integration tests for notification API routes."""
import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import User, UserRole
from app.models.notification import UserNotification, NotificationType, NotificationCategory
from app.services.auth_service import AuthService


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session):
    hashed = AuthService.hash_password("AdminPassword123!")
    user = User(
        username="notifadmin",
        email="notifadmin@example.com",
        hashed_password=hashed,
        role=UserRole.ADMIN.value,
        is_active=True,
        is_locked=False,
        failed_login_attempts=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def viewer_user(db_session):
    hashed = AuthService.hash_password("ViewerPassword123!")
    user = User(
        username="notifviewer",
        email="notifviewer@example.com",
        hashed_password=hashed,
        role=UserRole.VIEWER.value,
        is_active=True,
        is_locked=False,
        failed_login_attempts=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user):
    return AuthService.create_access_token(
        str(admin_user.id), admin_user.username, UserRole.ADMIN
    )


@pytest.fixture
def viewer_token(viewer_user):
    return AuthService.create_access_token(
        str(viewer_user.id), viewer_user.username, UserRole.VIEWER
    )


@pytest.fixture
def sample_notifications(db_session, viewer_user):
    """Create sample notifications for the viewer user."""
    notifications = []
    for i in range(3):
        n = UserNotification(
            user_id=viewer_user.id,
            title=f"Test Notification {i}",
            message=f"This is test notification {i}",
            notification_type=NotificationType.INFO,
            category=NotificationCategory.SYSTEM,
            is_read=(i == 0),  # First one is read
        )
        if i == 0:
            n.read_at = datetime.utcnow()
        db_session.add(n)
        notifications.append(n)
    db_session.commit()
    for n in notifications:
        db_session.refresh(n)
    return notifications


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
class TestListNotifications:
    """Test GET /api/notifications"""

    def test_list_notifications(self, client, viewer_token, viewer_user, sample_notifications):
        """List notifications for current user."""
        response = client.get(
            "/api/notifications", headers=auth_header(viewer_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert "notifications" in data
        assert "total" in data
        assert "unread_count" in data
        assert data["total"] == 3
        assert data["unread_count"] == 2

    def test_list_unread_only(self, client, viewer_token, viewer_user, sample_notifications):
        """List only unread notifications."""
        response = client.get(
            "/api/notifications?unread_only=true",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    def test_list_requires_auth(self, client):
        """Listing notifications requires authentication."""
        response = client.get("/api/notifications")
        assert response.status_code == 401


@pytest.mark.integration
class TestNotificationCount:
    """Test GET /api/notifications/count"""

    def test_get_counts(self, client, viewer_token, viewer_user, sample_notifications):
        """Get notification counts."""
        response = client.get(
            "/api/notifications/count", headers=auth_header(viewer_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "unread" in data
        assert data["total"] == 3
        assert data["unread"] == 2


@pytest.mark.integration
class TestMarkAsRead:
    """Test POST /api/notifications/{id}/read"""

    def test_mark_as_read(self, client, viewer_token, viewer_user, sample_notifications):
        """Mark a notification as read."""
        unread = sample_notifications[1]  # Second one is unread
        response = client.post(
            f"/api/notifications/{unread.id}/read",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_read"] is True

    def test_mark_nonexistent_as_read(self, client, viewer_token, viewer_user):
        """Marking non-existent notification returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.post(
            f"/api/notifications/{fake_id}/read",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestMarkAllRead:
    """Test POST /api/notifications/read-all"""

    def test_mark_all_read(self, client, viewer_token, viewer_user, sample_notifications):
        """Mark all notifications as read."""
        response = client.post(
            "/api/notifications/read-all",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 200
        assert "Marked" in response.json()["message"]


@pytest.mark.integration
class TestDeleteNotification:
    """Test DELETE /api/notifications/{id}"""

    def test_delete_notification(self, client, viewer_token, viewer_user, sample_notifications):
        """Delete a notification."""
        notif = sample_notifications[0]
        response = client.delete(
            f"/api/notifications/{notif.id}",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 204

    def test_delete_nonexistent(self, client, viewer_token, viewer_user):
        """Deleting non-existent notification returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.delete(
            f"/api/notifications/{fake_id}",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestCreateNotification:
    """Test POST /api/notifications (admin only)"""

    def test_admin_create_notification(self, client, admin_token, admin_user, viewer_user):
        """Admin can create a notification for a user."""
        response = client.post(
            "/api/notifications",
            json={
                "title": "Admin Alert",
                "message": "Important notification from admin",
                "notification_type": "warning",
                "category": "system",
                "user_id": str(viewer_user.id),
            },
            headers=auth_header(admin_token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Admin Alert"
        assert data["notification_type"] == "warning"

    def test_viewer_cannot_create(self, client, viewer_token, viewer_user):
        """Viewer cannot create notifications."""
        response = client.post(
            "/api/notifications",
            json={
                "title": "Forbidden",
                "message": "Should not work",
            },
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403


@pytest.mark.integration
class TestDeleteAllRead:
    """Test DELETE /api/notifications/read/all"""

    def test_delete_all_read(self, client, viewer_token, viewer_user, sample_notifications):
        """Delete all read notifications."""
        response = client.delete(
            "/api/notifications/read/all",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 200
        assert "Deleted" in response.json()["message"]
