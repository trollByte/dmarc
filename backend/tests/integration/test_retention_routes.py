"""Integration tests for data retention API routes."""
import pytest
import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import User, UserRole, RetentionPolicy
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
        username="retadmin",
        email="retadmin@example.com",
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
        username="retviewer",
        email="retviewer@example.com",
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
def sample_policy(db_session, admin_user):
    """Create a sample retention policy."""
    policy = RetentionPolicy(
        name="Test DMARC Reports Retention",
        target="dmarc_reports",
        retention_days=365,
        description="Keep reports for 1 year",
        is_enabled=False,
        created_by=admin_user.id,
    )
    db_session.add(policy)
    db_session.commit()
    db_session.refresh(policy)
    return policy


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
class TestListPolicies:
    """Test GET /api/retention/policies"""

    def test_list_policies_admin(self, client, admin_token, admin_user, sample_policy):
        """Admin can list retention policies."""
        response = client.get(
            "/api/retention/policies", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_policies_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot list retention policies."""
        response = client.get(
            "/api/retention/policies", headers=auth_header(viewer_token)
        )
        assert response.status_code == 403

    def test_list_policies_unauthenticated(self, client):
        """Unauthenticated returns 401."""
        response = client.get("/api/retention/policies")
        assert response.status_code == 401


@pytest.mark.integration
class TestCreatePolicy:
    """Test POST /api/retention/policies"""

    def test_create_policy(self, client, admin_token, admin_user):
        """Admin can create a retention policy."""
        response = client.post(
            "/api/retention/policies",
            json={
                "name": "Audit Logs 90 Days",
                "target": "audit_logs",
                "retention_days": 90,
                "description": "Keep audit logs for 90 days",
                "is_enabled": True,
            },
            headers=auth_header(admin_token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Audit Logs 90 Days"
        assert data["target"] == "audit_logs"
        assert data["retention_days"] == 90
        assert data["is_enabled"] is True

    def test_create_policy_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot create retention policies."""
        response = client.post(
            "/api/retention/policies",
            json={
                "name": "Forbidden",
                "target": "dmarc_reports",
                "retention_days": 30,
            },
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403


@pytest.mark.integration
class TestGetPolicy:
    """Test GET /api/retention/policies/{id}"""

    def test_get_policy(self, client, admin_token, admin_user, sample_policy):
        """Admin can get a specific policy."""
        response = client.get(
            f"/api/retention/policies/{sample_policy.id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test DMARC Reports Retention"

    def test_get_nonexistent_policy(self, client, admin_token, admin_user):
        """Non-existent policy returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(
            f"/api/retention/policies/{fake_id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestUpdatePolicy:
    """Test PUT /api/retention/policies/{id}"""

    def test_update_policy(self, client, admin_token, admin_user, sample_policy):
        """Admin can update a retention policy."""
        response = client.put(
            f"/api/retention/policies/{sample_policy.id}",
            json={
                "retention_days": 180,
                "is_enabled": True,
            },
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["retention_days"] == 180
        assert data["is_enabled"] is True


@pytest.mark.integration
class TestDeletePolicy:
    """Test DELETE /api/retention/policies/{id}"""

    def test_delete_policy(self, client, admin_token, admin_user, sample_policy):
        """Admin can delete a retention policy."""
        response = client.delete(
            f"/api/retention/policies/{sample_policy.id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 204

    def test_delete_nonexistent_policy(self, client, admin_token, admin_user):
        """Deleting non-existent policy returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.delete(
            f"/api/retention/policies/{fake_id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestPreviewPolicy:
    """Test GET /api/retention/policies/{id}/preview"""

    def test_preview_policy(self, client, admin_token, admin_user, sample_policy):
        """Admin can preview policy execution."""
        response = client.get(
            f"/api/retention/policies/{sample_policy.id}/preview",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200

    def test_preview_nonexistent_policy(self, client, admin_token, admin_user):
        """Preview non-existent policy returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(
            f"/api/retention/policies/{fake_id}/preview",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestRetentionLogs:
    """Test GET /api/retention/logs"""

    def test_get_logs(self, client, admin_token, admin_user):
        """Admin can get retention logs."""
        response = client.get(
            "/api/retention/logs", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_logs_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot access retention logs."""
        response = client.get(
            "/api/retention/logs", headers=auth_header(viewer_token)
        )
        assert response.status_code == 403


@pytest.mark.integration
class TestRetentionStats:
    """Test GET /api/retention/stats"""

    def test_get_stats(self, client, admin_token, admin_user):
        """Admin can get retention stats."""
        response = client.get(
            "/api/retention/stats", headers=auth_header(admin_token)
        )
        assert response.status_code == 200

    def test_stats_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot access retention stats."""
        response = client.get(
            "/api/retention/stats", headers=auth_header(viewer_token)
        )
        assert response.status_code == 403


@pytest.mark.integration
class TestInitDefaults:
    """Test POST /api/retention/init-defaults"""

    def test_init_defaults(self, client, admin_token, admin_user):
        """Admin can initialize default policies."""
        response = client.post(
            "/api/retention/init-defaults",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 201
        data = response.json()
        assert isinstance(data, list)
