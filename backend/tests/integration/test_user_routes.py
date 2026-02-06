"""Integration tests for user management API routes."""
import pytest
import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import User, UserRole, UserAPIKey
from app.services.auth_service import AuthService


@pytest.fixture
def client(db_session):
    """Create test client with database dependency override"""
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
    """Create an admin user with real hashed password."""
    hashed = AuthService.hash_password("AdminPassword123!")
    user = User(
        username="admin",
        email="admin@example.com",
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
    """Create a viewer user."""
    hashed = AuthService.hash_password("ViewerPassword123!")
    user = User(
        username="viewer",
        email="viewer@example.com",
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
    """Generate admin access token."""
    return AuthService.create_access_token(
        str(admin_user.id), admin_user.username, UserRole.ADMIN
    )


@pytest.fixture
def viewer_token(viewer_user):
    """Generate viewer access token."""
    return AuthService.create_access_token(
        str(viewer_user.id), viewer_user.username, UserRole.VIEWER
    )


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
class TestListUsers:
    """Test GET /api/users"""

    def test_list_users_admin(self, client, admin_token, admin_user, viewer_user):
        """Admin can list all users."""
        response = client.get("/api/users", headers=auth_header(admin_token))
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        assert len(data["users"]) >= 2
        assert "page" in data
        assert "page_size" in data

    def test_list_users_pagination(self, client, admin_token, admin_user, viewer_user):
        """List users with pagination."""
        response = client.get(
            "/api/users?page=1&page_size=1", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        assert len(data["users"]) == 1
        assert data["page"] == 1
        assert data["page_size"] == 1

    def test_list_users_viewer_forbidden(self, client, viewer_token):
        """Viewer cannot list users."""
        response = client.get("/api/users", headers=auth_header(viewer_token))
        assert response.status_code == 403

    def test_list_users_unauthenticated(self, client):
        """Unauthenticated request returns 401."""
        response = client.get("/api/users")
        assert response.status_code == 401


@pytest.mark.integration
class TestCreateUser:
    """Test POST /api/users"""

    def test_create_user_admin(self, client, admin_token, admin_user):
        """Admin can create a new user."""
        response = client.post(
            "/api/users",
            json={
                "username": "newanalyst",
                "email": "analyst@example.com",
                "password": "AnalystPass123!",
                "role": "analyst",
            },
            headers=auth_header(admin_token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newanalyst"
        assert data["email"] == "analyst@example.com"
        assert data["role"] == "analyst"
        assert data["is_active"] is True

    def test_create_user_duplicate_username(self, client, admin_token, admin_user):
        """Duplicate username returns 400."""
        response = client.post(
            "/api/users",
            json={
                "username": "admin",
                "email": "another@example.com",
                "password": "ValidPassword123!",
            },
            headers=auth_header(admin_token),
        )
        assert response.status_code == 400
        assert "Username already exists" in response.json()["detail"]

    def test_create_user_duplicate_email(self, client, admin_token, admin_user):
        """Duplicate email returns 400."""
        response = client.post(
            "/api/users",
            json={
                "username": "unique",
                "email": "admin@example.com",
                "password": "ValidPassword123!",
            },
            headers=auth_header(admin_token),
        )
        assert response.status_code == 400
        assert "Email already exists" in response.json()["detail"]

    def test_create_user_weak_password(self, client, admin_token, admin_user):
        """Weak password returns 400."""
        response = client.post(
            "/api/users",
            json={
                "username": "weakuser",
                "email": "weak@example.com",
                "password": "short",
            },
            headers=auth_header(admin_token),
        )
        assert response.status_code == 422

    def test_create_user_viewer_forbidden(self, client, viewer_token):
        """Viewer cannot create users."""
        response = client.post(
            "/api/users",
            json={
                "username": "x",
                "email": "x@example.com",
                "password": "SecurePassword123!",
            },
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403


@pytest.mark.integration
class TestGetUser:
    """Test GET /api/users/{user_id}"""

    def test_get_own_profile(self, client, admin_token, admin_user):
        """User can view own profile."""
        response = client.get(
            f"/api/users/{admin_user.id}", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"

    def test_admin_get_other_profile(self, client, admin_token, admin_user, viewer_user):
        """Admin can view other user's profile."""
        response = client.get(
            f"/api/users/{viewer_user.id}", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        assert response.json()["username"] == "viewer"

    def test_viewer_cannot_view_other(self, client, viewer_token, admin_user):
        """Viewer cannot view other user's profile."""
        response = client.get(
            f"/api/users/{admin_user.id}", headers=auth_header(viewer_token)
        )
        assert response.status_code == 403

    def test_get_nonexistent_user(self, client, admin_token, admin_user):
        """Non-existent user returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(
            f"/api/users/{fake_id}", headers=auth_header(admin_token)
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestUpdateUser:
    """Test PATCH /api/users/{user_id}"""

    def test_update_own_email(self, client, admin_token, admin_user):
        """User can update own email."""
        response = client.patch(
            f"/api/users/{admin_user.id}",
            json={"email": "newemail@example.com"},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert response.json()["email"] == "newemail@example.com"

    def test_admin_update_role(self, client, admin_token, admin_user, viewer_user):
        """Admin can change another user's role."""
        response = client.patch(
            f"/api/users/{viewer_user.id}",
            json={"role": "analyst"},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert response.json()["role"] == "analyst"

    def test_viewer_cannot_change_role(self, client, viewer_token, viewer_user):
        """Non-admin cannot change roles."""
        response = client.patch(
            f"/api/users/{viewer_user.id}",
            json={"role": "admin"},
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403

    def test_update_nonexistent_user(self, client, admin_token, admin_user):
        """Updating non-existent user returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.patch(
            f"/api/users/{fake_id}",
            json={"email": "x@example.com"},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestDeleteUser:
    """Test DELETE /api/users/{user_id}"""

    def test_admin_delete_user(self, client, admin_token, admin_user, viewer_user):
        """Admin can delete a user."""
        response = client.delete(
            f"/api/users/{viewer_user.id}", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()

    def test_cannot_delete_self(self, client, admin_token, admin_user):
        """Admin cannot delete own account."""
        response = client.delete(
            f"/api/users/{admin_user.id}", headers=auth_header(admin_token)
        )
        assert response.status_code == 400

    def test_delete_nonexistent_user(self, client, admin_token, admin_user):
        """Deleting non-existent user returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.delete(
            f"/api/users/{fake_id}", headers=auth_header(admin_token)
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestUnlockAccount:
    """Test POST /api/users/{user_id}/unlock"""

    def test_unlock_locked_account(self, client, db_session, admin_token, admin_user):
        """Admin can unlock a locked account."""
        hashed = AuthService.hash_password("LockedPassword123!")
        locked = User(
            username="lockeduser",
            email="locked@example.com",
            hashed_password=hashed,
            role=UserRole.VIEWER.value,
            is_active=True,
            is_locked=True,
            failed_login_attempts=5,
        )
        db_session.add(locked)
        db_session.commit()
        db_session.refresh(locked)

        response = client.post(
            f"/api/users/{locked.id}/unlock", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        assert response.json()["is_locked"] is False

    def test_unlock_not_locked(self, client, admin_token, admin_user, viewer_user):
        """Unlocking a non-locked account returns 400."""
        response = client.post(
            f"/api/users/{viewer_user.id}/unlock", headers=auth_header(admin_token)
        )
        assert response.status_code == 400


@pytest.mark.integration
class TestAPIKeys:
    """Test API key management endpoints."""

    def test_create_api_key(self, client, admin_token, admin_user):
        """Create a new API key."""
        response = client.post(
            "/api/users/me/api-keys",
            json={"key_name": "Test Key", "expires_days": 30},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["key_name"] == "Test Key"
        assert "api_key" in data
        assert data["api_key"].startswith("dmarc_")
        assert data["key_prefix"] is not None

    def test_list_api_keys(self, client, admin_token, admin_user):
        """List user's API keys."""
        # Create a key first
        client.post(
            "/api/users/me/api-keys",
            json={"key_name": "Key1"},
            headers=auth_header(admin_token),
        )

        response = client.get(
            "/api/users/me/api-keys", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["key_name"] == "Key1"

    def test_delete_api_key(self, client, admin_token, admin_user):
        """Delete an API key."""
        # Create a key first
        create_resp = client.post(
            "/api/users/me/api-keys",
            json={"key_name": "ToDelete"},
            headers=auth_header(admin_token),
        )
        key_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/users/me/api-keys/{key_id}", headers=auth_header(admin_token)
        )
        assert response.status_code == 200

    def test_delete_nonexistent_key(self, client, admin_token, admin_user):
        """Deleting non-existent API key returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.delete(
            f"/api/users/me/api-keys/{fake_id}", headers=auth_header(admin_token)
        )
        assert response.status_code == 404
