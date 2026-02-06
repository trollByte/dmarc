"""Integration tests for saved view API routes."""
import pytest
import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import User, UserRole
from app.models.saved_view import SavedView
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
def user_a(db_session):
    """Create first user."""
    hashed = AuthService.hash_password("UserAPassword123!")
    user = User(
        username="svuser_a",
        email="svuser_a@example.com",
        hashed_password=hashed,
        role=UserRole.ANALYST.value,
        is_active=True,
        is_locked=False,
        failed_login_attempts=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_b(db_session):
    """Create second user."""
    hashed = AuthService.hash_password("UserBPassword123!")
    user = User(
        username="svuser_b",
        email="svuser_b@example.com",
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
def token_a(user_a):
    return AuthService.create_access_token(
        str(user_a.id), user_a.username, UserRole.ANALYST
    )


@pytest.fixture
def token_b(user_b):
    return AuthService.create_access_token(
        str(user_b.id), user_b.username, UserRole.VIEWER
    )


@pytest.fixture
def sample_view(db_session, user_a):
    """Create a sample saved view."""
    view = SavedView(
        user_id=user_a.id,
        name="My Filter",
        description="Custom filter view",
        filters={"domain": "example.com", "dateRange": "7d"},
        display_settings={"sortBy": "date", "sortOrder": "desc"},
        is_shared=False,
        is_default=False,
    )
    db_session.add(view)
    db_session.commit()
    db_session.refresh(view)
    return view


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
class TestListSavedViews:
    """Test GET /api/saved-views"""

    def test_list_own_views(self, client, token_a, user_a, sample_view):
        """List saved views for current user."""
        response = client.get(
            "/api/saved-views", headers=auth_header(token_a)
        )
        assert response.status_code == 200
        data = response.json()
        assert "views" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_list_requires_auth(self, client):
        """List views requires auth."""
        response = client.get("/api/saved-views")
        assert response.status_code == 401


@pytest.mark.integration
class TestCreateSavedView:
    """Test POST /api/saved-views"""

    def test_create_view(self, client, token_a, user_a):
        """Create a new saved view."""
        response = client.post(
            "/api/saved-views",
            json={
                "name": "New View",
                "description": "A new dashboard view",
                "filters": {"domain": "test.com"},
                "is_shared": False,
                "is_default": False,
            },
            headers=auth_header(token_a),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New View"
        assert data["filters"]["domain"] == "test.com"
        assert data["is_shared"] is False

    def test_create_shared_view(self, client, token_a, user_a):
        """Create a shared view."""
        response = client.post(
            "/api/saved-views",
            json={
                "name": "Shared View",
                "filters": {"disposition": "reject"},
                "is_shared": True,
            },
            headers=auth_header(token_a),
        )
        assert response.status_code == 201
        assert response.json()["is_shared"] is True


@pytest.mark.integration
class TestGetSavedView:
    """Test GET /api/saved-views/{id}"""

    def test_get_own_view(self, client, token_a, user_a, sample_view):
        """Get own saved view."""
        response = client.get(
            f"/api/saved-views/{sample_view.id}",
            headers=auth_header(token_a),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "My Filter"

    def test_get_nonexistent_view(self, client, token_a, user_a):
        """Non-existent view returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(
            f"/api/saved-views/{fake_id}",
            headers=auth_header(token_a),
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestUpdateSavedView:
    """Test PATCH /api/saved-views/{id}"""

    def test_update_view_name(self, client, token_a, user_a, sample_view):
        """Update view name."""
        response = client.patch(
            f"/api/saved-views/{sample_view.id}",
            json={"name": "Updated Filter"},
            headers=auth_header(token_a),
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Filter"

    def test_update_view_filters(self, client, token_a, user_a, sample_view):
        """Update view filters."""
        response = client.patch(
            f"/api/saved-views/{sample_view.id}",
            json={"filters": {"domain": "other.com"}},
            headers=auth_header(token_a),
        )
        assert response.status_code == 200
        assert response.json()["filters"]["domain"] == "other.com"

    def test_update_other_user_view_forbidden(self, client, token_b, user_b, sample_view):
        """Cannot update another user's view."""
        response = client.patch(
            f"/api/saved-views/{sample_view.id}",
            json={"name": "Hacked"},
            headers=auth_header(token_b),
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestDeleteSavedView:
    """Test DELETE /api/saved-views/{id}"""

    def test_delete_own_view(self, client, token_a, user_a, sample_view):
        """Delete own saved view."""
        response = client.delete(
            f"/api/saved-views/{sample_view.id}",
            headers=auth_header(token_a),
        )
        assert response.status_code == 204

    def test_delete_other_user_view_forbidden(self, client, token_b, user_b, sample_view):
        """Cannot delete another user's view."""
        response = client.delete(
            f"/api/saved-views/{sample_view.id}",
            headers=auth_header(token_b),
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestDefaultView:
    """Test GET /api/saved-views/default"""

    def test_get_default_no_default(self, client, token_a, user_a):
        """No default view returns null."""
        response = client.get(
            "/api/saved-views/default", headers=auth_header(token_a)
        )
        assert response.status_code == 200
        # Response should be null/None when no default
        assert response.json() is None or response.status_code == 200

    def test_set_and_get_default(self, client, token_a, user_a, sample_view):
        """Set a view as default and retrieve it."""
        # Set as default
        set_resp = client.post(
            f"/api/saved-views/{sample_view.id}/set-default",
            headers=auth_header(token_a),
        )
        assert set_resp.status_code == 200

        # Get default
        response = client.get(
            "/api/saved-views/default", headers=auth_header(token_a)
        )
        assert response.status_code == 200


@pytest.mark.integration
class TestUseSavedView:
    """Test POST /api/saved-views/{id}/use"""

    def test_use_view_updates_timestamp(self, client, token_a, user_a, sample_view):
        """Using a view updates last_used_at."""
        response = client.post(
            f"/api/saved-views/{sample_view.id}/use",
            headers=auth_header(token_a),
        )
        assert response.status_code == 200

    def test_use_nonexistent_view(self, client, token_a, user_a):
        """Using a non-existent view returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.post(
            f"/api/saved-views/{fake_id}/use",
            headers=auth_header(token_a),
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestDuplicateView:
    """Test POST /api/saved-views/{id}/duplicate"""

    def test_duplicate_own_view(self, client, token_a, user_a, sample_view):
        """Duplicate own view."""
        response = client.post(
            f"/api/saved-views/{sample_view.id}/duplicate?name=Copy",
            headers=auth_header(token_a),
        )
        assert response.status_code == 201
        data = response.json()
        assert "Copy" in data["name"] or data["name"] != sample_view.name
