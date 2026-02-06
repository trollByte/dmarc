"""Integration tests for webhook API routes."""
import pytest
import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import User, UserRole
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
        username="webhookadmin",
        email="webhookadmin@example.com",
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
        username="webhookviewer",
        email="webhookviewer@example.com",
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


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
class TestListWebhookEvents:
    """Test GET /api/webhooks/events"""

    def test_list_events(self, client, admin_token, admin_user):
        """List available webhook events."""
        response = client.get(
            "/api/webhooks/events", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Verify known events exist
        assert "alert.created" in data
        assert "report.received" in data

    def test_list_events_any_user(self, client, viewer_token, viewer_user):
        """Any authenticated user can list events."""
        response = client.get(
            "/api/webhooks/events", headers=auth_header(viewer_token)
        )
        assert response.status_code == 200


@pytest.mark.integration
class TestCreateWebhookEndpoint:
    """Test POST /api/webhooks"""

    def test_create_endpoint(self, client, admin_token, admin_user):
        """Admin can create a webhook endpoint."""
        response = client.post(
            "/api/webhooks",
            json={
                "name": "Test Webhook",
                "url": "https://hooks.example.com/dmarc",
                "events": ["alert.created", "report.received"],
                "generate_secret": True,
            },
            headers=auth_header(admin_token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Webhook"
        assert "secret" in data
        assert data["secret"] != "No secret configured"

    def test_create_endpoint_no_secret(self, client, admin_token, admin_user):
        """Create endpoint without secret."""
        response = client.post(
            "/api/webhooks",
            json={
                "name": "No Secret Webhook",
                "url": "https://hooks.example.com/nosecret",
                "events": ["alert.created"],
                "generate_secret": False,
            },
            headers=auth_header(admin_token),
        )
        assert response.status_code == 201

    def test_create_endpoint_invalid_event(self, client, admin_token, admin_user):
        """Invalid event type returns 400."""
        response = client.post(
            "/api/webhooks",
            json={
                "name": "Bad Events Webhook",
                "url": "https://hooks.example.com/bad",
                "events": ["invalid.event"],
            },
            headers=auth_header(admin_token),
        )
        assert response.status_code == 400

    def test_create_endpoint_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot create webhook endpoints."""
        response = client.post(
            "/api/webhooks",
            json={
                "name": "Forbidden",
                "url": "https://hooks.example.com/nope",
                "events": ["alert.created"],
            },
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403


@pytest.mark.integration
class TestListWebhookEndpoints:
    """Test GET /api/webhooks"""

    def test_list_endpoints(self, client, admin_token, admin_user):
        """Admin can list webhook endpoints."""
        # Create one first
        client.post(
            "/api/webhooks",
            json={
                "name": "Listed Webhook",
                "url": "https://hooks.example.com/list",
                "events": ["alert.created"],
            },
            headers=auth_header(admin_token),
        )

        response = client.get(
            "/api/webhooks", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_endpoints_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot list webhook endpoints."""
        response = client.get(
            "/api/webhooks", headers=auth_header(viewer_token)
        )
        assert response.status_code == 403


@pytest.mark.integration
class TestGetWebhookEndpoint:
    """Test GET /api/webhooks/{id}"""

    def test_get_endpoint(self, client, admin_token, admin_user):
        """Admin can get endpoint details."""
        # Create one first
        create_resp = client.post(
            "/api/webhooks",
            json={
                "name": "Get Detail Webhook",
                "url": "https://hooks.example.com/detail",
                "events": ["alert.created"],
            },
            headers=auth_header(admin_token),
        )
        endpoint_id = create_resp.json()["id"]

        response = client.get(
            f"/api/webhooks/{endpoint_id}", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Get Detail Webhook"
        assert data["url"] == "https://hooks.example.com/detail"

    def test_get_nonexistent_endpoint(self, client, admin_token, admin_user):
        """Non-existent endpoint returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(
            f"/api/webhooks/{fake_id}", headers=auth_header(admin_token)
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestUpdateWebhookEndpoint:
    """Test PUT /api/webhooks/{id}"""

    def test_update_endpoint(self, client, admin_token, admin_user):
        """Admin can update a webhook endpoint."""
        # Create one
        create_resp = client.post(
            "/api/webhooks",
            json={
                "name": "Update Me",
                "url": "https://hooks.example.com/update",
                "events": ["alert.created"],
            },
            headers=auth_header(admin_token),
        )
        endpoint_id = create_resp.json()["id"]

        response = client.put(
            f"/api/webhooks/{endpoint_id}",
            json={"name": "Updated Webhook", "is_enabled": False},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Webhook"
        assert data["is_enabled"] is False

    def test_update_nonexistent_endpoint(self, client, admin_token, admin_user):
        """Updating non-existent endpoint returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.put(
            f"/api/webhooks/{fake_id}",
            json={"name": "X"},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestDeleteWebhookEndpoint:
    """Test DELETE /api/webhooks/{id}"""

    def test_delete_endpoint(self, client, admin_token, admin_user):
        """Admin can delete a webhook endpoint."""
        # Create one
        create_resp = client.post(
            "/api/webhooks",
            json={
                "name": "Delete Me",
                "url": "https://hooks.example.com/delete",
                "events": ["alert.created"],
            },
            headers=auth_header(admin_token),
        )
        endpoint_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/webhooks/{endpoint_id}", headers=auth_header(admin_token)
        )
        assert response.status_code == 204

    def test_delete_nonexistent_endpoint(self, client, admin_token, admin_user):
        """Deleting non-existent endpoint returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.delete(
            f"/api/webhooks/{fake_id}", headers=auth_header(admin_token)
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestWebhookDeliveries:
    """Test GET /api/webhooks/{id}/deliveries"""

    def test_get_deliveries(self, client, admin_token, admin_user):
        """Get delivery history for an endpoint."""
        # Create an endpoint
        create_resp = client.post(
            "/api/webhooks",
            json={
                "name": "Deliveries Webhook",
                "url": "https://hooks.example.com/deliveries",
                "events": ["alert.created"],
            },
            headers=auth_header(admin_token),
        )
        endpoint_id = create_resp.json()["id"]

        response = client.get(
            f"/api/webhooks/{endpoint_id}/deliveries",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
