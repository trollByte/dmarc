"""Integration tests for audit log API routes."""
import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import User, UserRole, AuditLog
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
        username="auditadmin",
        email="auditadmin@example.com",
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
        username="auditviewer",
        email="auditviewer@example.com",
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
def sample_audit_logs(db_session, admin_user):
    """Seed some audit log entries."""
    logs = []
    for i in range(3):
        log = AuditLog(
            action=f"test_action_{i}",
            category="authentication",
            user_id=admin_user.id,
            username=admin_user.username,
            ip_address="127.0.0.1",
            user_agent="test-agent",
            target_type="user",
            target_id=str(admin_user.id),
            extra_data={"info": f"test log {i}"},
        )
        db_session.add(log)
        logs.append(log)
    db_session.commit()
    for log in logs:
        db_session.refresh(log)
    return logs


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
class TestListAuditLogs:
    """Test GET /api/audit/logs"""

    def test_list_logs_admin(self, client, admin_token, admin_user, sample_audit_logs):
        """Admin can list audit logs."""
        response = client.get(
            "/api/audit/logs", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert data["total"] >= 3

    def test_list_logs_pagination(self, client, admin_token, admin_user, sample_audit_logs):
        """List audit logs with pagination."""
        response = client.get(
            "/api/audit/logs?page=1&page_size=10",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_list_logs_filter_action(self, client, admin_token, admin_user, sample_audit_logs):
        """Filter audit logs by action."""
        response = client.get(
            "/api/audit/logs?action=test_action_0",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200

    def test_list_logs_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot access audit logs."""
        response = client.get(
            "/api/audit/logs", headers=auth_header(viewer_token)
        )
        assert response.status_code == 403

    def test_list_logs_unauthenticated(self, client):
        """Unauthenticated access returns 401."""
        response = client.get("/api/audit/logs")
        assert response.status_code == 401


@pytest.mark.integration
class TestAuditLogDetail:
    """Test GET /api/audit/logs/{id}"""

    def test_get_log_detail(self, client, admin_token, admin_user, sample_audit_logs):
        """Admin can get log detail."""
        log_id = sample_audit_logs[0].id
        response = client.get(
            f"/api/audit/logs/{log_id}", headers=auth_header(admin_token)
        )
        assert response.status_code == 200

    def test_get_nonexistent_log(self, client, admin_token, admin_user):
        """Non-existent log returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(
            f"/api/audit/logs/{fake_id}", headers=auth_header(admin_token)
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestAuditStats:
    """Test GET /api/audit/stats"""

    def test_get_audit_stats(self, client, admin_token, admin_user, sample_audit_logs):
        """Admin can get audit statistics."""
        response = client.get(
            "/api/audit/stats?days=30", headers=auth_header(admin_token)
        )
        assert response.status_code == 200

    def test_stats_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot access audit stats."""
        response = client.get(
            "/api/audit/stats", headers=auth_header(viewer_token)
        )
        assert response.status_code == 403


@pytest.mark.integration
class TestSecurityEvents:
    """Test GET /api/audit/security"""

    def test_get_security_events(self, client, admin_token, admin_user):
        """Admin can get security events."""
        response = client.get(
            "/api/audit/security?days=7", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_security_events_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot access security events."""
        response = client.get(
            "/api/audit/security", headers=auth_header(viewer_token)
        )
        assert response.status_code == 403


@pytest.mark.integration
class TestUserActivity:
    """Test GET /api/audit/user/{user_id}"""

    def test_get_user_activity(self, client, admin_token, admin_user, sample_audit_logs):
        """Admin can get user activity."""
        response = client.get(
            f"/api/audit/user/{admin_user.id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)


@pytest.mark.integration
class TestMyActivity:
    """Test GET /api/audit/my-activity"""

    def test_get_my_activity(self, client, admin_token, admin_user):
        """Any user can get their own activity."""
        response = client.get(
            "/api/audit/my-activity", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_my_activity_viewer(self, client, viewer_token, viewer_user):
        """Viewer can access their own activity."""
        response = client.get(
            "/api/audit/my-activity", headers=auth_header(viewer_token)
        )
        assert response.status_code == 200
