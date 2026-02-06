"""Integration tests for authentication API routes."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import User, UserRole, RefreshToken
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
def test_password():
    return "SecurePassword123!"


@pytest.fixture
def auth_user(db_session, test_password):
    """Create a user with a properly hashed password for auth tests."""
    hashed = AuthService.hash_password(test_password)
    user = User(
        username="authuser",
        email="auth@example.com",
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
def auth_tokens(auth_user):
    """Generate access + refresh token pair for the auth user."""
    access_token, refresh_token = AuthService.create_token_pair(auth_user)
    return {"access_token": access_token, "refresh_token": refresh_token}


@pytest.fixture
def stored_refresh_token(db_session, auth_user, auth_tokens):
    """Store the refresh token in the database so validation works."""
    AuthService.store_refresh_token(
        db_session,
        str(auth_user.id),
        auth_tokens["refresh_token"],
        user_agent="test-agent",
        ip_address="127.0.0.1",
    )
    return auth_tokens["refresh_token"]


@pytest.mark.integration
class TestLogin:
    """Test POST /api/auth/login"""

    def test_login_valid_credentials(self, client, auth_user, test_password):
        """Valid credentials return tokens."""
        response = client.post(
            "/api/auth/login",
            json={"username": "authuser", "password": test_password},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    def test_login_invalid_password(self, client, auth_user):
        """Invalid password returns 401."""
        response = client.post(
            "/api/auth/login",
            json={"username": "authuser", "password": "WrongPassword123!"},
        )
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    def test_login_nonexistent_user(self, client):
        """Non-existent user returns 401."""
        response = client.post(
            "/api/auth/login",
            json={"username": "nouser", "password": "SomePassword123!"},
        )
        assert response.status_code == 401

    def test_login_missing_fields(self, client):
        """Missing required fields returns 422."""
        response = client.post("/api/auth/login", json={"username": "authuser"})
        assert response.status_code == 422

    def test_login_inactive_user(self, client, db_session, test_password):
        """Inactive user returns 403."""
        hashed = AuthService.hash_password(test_password)
        user = User(
            username="inactive",
            email="inactive@example.com",
            hashed_password=hashed,
            role=UserRole.VIEWER.value,
            is_active=False,
            is_locked=False,
            failed_login_attempts=0,
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/login",
            json={"username": "inactive", "password": test_password},
        )
        assert response.status_code == 403
        assert "inactive" in response.json()["detail"].lower()

    def test_login_locked_user(self, client, db_session, test_password):
        """Locked user returns 403."""
        hashed = AuthService.hash_password(test_password)
        user = User(
            username="locked",
            email="locked@example.com",
            hashed_password=hashed,
            role=UserRole.VIEWER.value,
            is_active=True,
            is_locked=True,
            failed_login_attempts=5,
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/login",
            json={"username": "locked", "password": test_password},
        )
        assert response.status_code == 403
        assert "locked" in response.json()["detail"].lower()


@pytest.mark.integration
class TestRefreshToken:
    """Test POST /api/auth/refresh"""

    def test_refresh_valid_token(self, client, stored_refresh_token):
        """Valid refresh token returns new access token."""
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": stored_refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    def test_refresh_invalid_token(self, client):
        """Invalid refresh token returns 401."""
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": "invalid-token-value"},
        )
        assert response.status_code == 401

    def test_refresh_missing_token(self, client):
        """Missing refresh token returns 422."""
        response = client.post("/api/auth/refresh", json={})
        assert response.status_code == 422


@pytest.mark.integration
class TestLogout:
    """Test POST /api/auth/logout"""

    def test_logout_success(self, client, auth_tokens, stored_refresh_token):
        """Successful logout with valid token."""
        response = client.post(
            "/api/auth/logout",
            json={"refresh_token": stored_refresh_token},
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )
        assert response.status_code == 200
        assert "Logged out" in response.json()["message"]

    def test_logout_requires_auth(self, client, stored_refresh_token):
        """Logout requires authentication."""
        response = client.post(
            "/api/auth/logout",
            json={"refresh_token": stored_refresh_token},
        )
        assert response.status_code == 401


@pytest.mark.integration
class TestLogoutAll:
    """Test POST /api/auth/logout/all"""

    def test_logout_all_success(self, client, auth_tokens, stored_refresh_token):
        """Successful logout all sessions."""
        response = client.post(
            "/api/auth/logout/all",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )
        assert response.status_code == 200
        assert "Logged out" in response.json()["message"]

    def test_logout_all_requires_auth(self, client):
        """Logout all requires authentication."""
        response = client.post("/api/auth/logout/all")
        assert response.status_code == 401


@pytest.mark.integration
class TestGetMe:
    """Test GET /api/auth/me"""

    def test_get_me_returns_user(self, client, auth_tokens, auth_user):
        """Returns current user info."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert data["user"]["username"] == "authuser"
        assert data["user"]["email"] == "auth@example.com"
        assert "permissions" in data

    def test_get_me_requires_auth(self, client):
        """Get me requires authentication."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401


@pytest.mark.integration
class TestPasswordReset:
    """Test password reset endpoints."""

    def test_request_reset_always_succeeds(self, client):
        """Password reset request always returns success to prevent enumeration."""
        response = client.post(
            "/api/auth/password-reset/request",
            json={"email": "nonexistent@example.com"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_validate_invalid_token(self, client):
        """Invalid reset token returns 400."""
        response = client.post(
            "/api/auth/password-reset/validate",
            json={"token": "invalid-reset-token"},
        )
        assert response.status_code == 400
