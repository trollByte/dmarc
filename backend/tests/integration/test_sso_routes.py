"""Integration tests for SAML and OAuth SSO API routes."""
import pytest
import uuid
from unittest.mock import patch, MagicMock
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
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session):
    hashed = AuthService.hash_password("AdminPassword123!")
    user = User(
        username="ssoadmin",
        email="ssoadmin@example.com",
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
        username="ssoviewer",
        email="ssoviewer@example.com",
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
def analyst_user(db_session):
    hashed = AuthService.hash_password("AnalystPassword123!")
    user = User(
        username="ssoanalyst",
        email="ssoanalyst@example.com",
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
def analyst_token(analyst_user):
    return AuthService.create_access_token(
        str(analyst_user.id), analyst_user.username, UserRole.ANALYST
    )


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


SAMPLE_CERT = (
    "MIICpDCCAYwCCQDU+pQ4pWlHVDANBgkqhkiG9w0BAQsFADAUMRIwEAYDVQQDDAls"
    "b2NhbGhvc3QwHhcNMjMwMTAxMDAwMDAwWhcNMjQwMTAxMDAwMDAwWjAUMRIwEAYD"
    "VQQDDAlsb2NhbGhvc3QwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQC7"
)


def _create_saml_provider_payload(**overrides):
    """Helper to build a valid SAML provider payload."""
    payload = {
        "name": "Test IdP",
        "entity_id": f"https://idp.example.com/metadata/{uuid.uuid4().hex[:8]}",
        "sso_url": "https://idp.example.com/sso",
        "x509_cert": SAMPLE_CERT,
        "slo_url": "https://idp.example.com/slo",
        "auto_provision_users": True,
        "default_role": "viewer",
    }
    payload.update(overrides)
    return payload


# ============================================================
#  SAML Provider CRUD
# ============================================================

@pytest.mark.integration
class TestListSAMLProviders:
    """Test GET /api/saml/providers"""

    def test_list_providers_unauthenticated(self, client):
        """Listing SAML providers does not require authentication."""
        response = client.get("/api/saml/providers")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_providers_empty(self, client):
        """Empty list when no providers configured."""
        response = client.get("/api/saml/providers")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_providers_after_create(self, client, admin_token, admin_user):
        """Providers appear after creation."""
        client.post(
            "/api/saml/providers",
            json=_create_saml_provider_payload(name="Listed IdP"),
            headers=auth_header(admin_token),
        )

        response = client.get("/api/saml/providers")
        assert response.status_code == 200
        names = [p["name"] for p in response.json()]
        assert "Listed IdP" in names


@pytest.mark.integration
class TestCreateSAMLProvider:
    """Test POST /api/saml/providers"""

    def test_create_provider_admin(self, client, admin_token, admin_user):
        """Admin can create a SAML provider."""
        payload = _create_saml_provider_payload(name="New IdP")
        response = client.post(
            "/api/saml/providers",
            json=payload,
            headers=auth_header(admin_token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New IdP"
        assert data["is_active"] is True
        assert data["auto_provision_users"] is True
        assert "id" in data
        assert "created_at" in data

    def test_create_provider_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot create SAML providers."""
        response = client.post(
            "/api/saml/providers",
            json=_create_saml_provider_payload(),
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403

    def test_create_provider_analyst_forbidden(self, client, analyst_token, analyst_user):
        """Analyst cannot create SAML providers."""
        response = client.post(
            "/api/saml/providers",
            json=_create_saml_provider_payload(),
            headers=auth_header(analyst_token),
        )
        assert response.status_code == 403

    def test_create_provider_missing_fields(self, client, admin_token, admin_user):
        """Missing required fields returns 422."""
        response = client.post(
            "/api/saml/providers",
            json={"name": "Incomplete"},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 422

    def test_create_provider_unauthenticated(self, client):
        """Unauthenticated create returns 401/403."""
        response = client.post(
            "/api/saml/providers",
            json=_create_saml_provider_payload(),
        )
        assert response.status_code in (401, 403)


@pytest.mark.integration
class TestGetSAMLProvider:
    """Test GET /api/saml/providers/{id}"""

    def test_get_provider(self, client, admin_token, admin_user):
        """Admin can get provider details."""
        create_resp = client.post(
            "/api/saml/providers",
            json=_create_saml_provider_payload(name="Detail IdP"),
            headers=auth_header(admin_token),
        )
        provider_id = create_resp.json()["id"]

        response = client.get(
            f"/api/saml/providers/{provider_id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Detail IdP"

    def test_get_provider_not_found(self, client, admin_token, admin_user):
        """Non-existent provider returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(
            f"/api/saml/providers/{fake_id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404

    def test_get_provider_viewer_forbidden(self, client, admin_token, admin_user, viewer_token, viewer_user):
        """Viewer cannot get provider details (admin only)."""
        create_resp = client.post(
            "/api/saml/providers",
            json=_create_saml_provider_payload(name="Admin Only IdP"),
            headers=auth_header(admin_token),
        )
        provider_id = create_resp.json()["id"]

        response = client.get(
            f"/api/saml/providers/{provider_id}",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403


@pytest.mark.integration
class TestUpdateSAMLProvider:
    """Test PUT /api/saml/providers/{id}"""

    def test_update_provider(self, client, admin_token, admin_user):
        """Admin can update provider fields."""
        create_resp = client.post(
            "/api/saml/providers",
            json=_create_saml_provider_payload(name="Before Update"),
            headers=auth_header(admin_token),
        )
        provider_id = create_resp.json()["id"]

        response = client.put(
            f"/api/saml/providers/{provider_id}",
            json={"name": "After Update", "is_active": False},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "After Update"
        assert data["is_active"] is False

    def test_update_provider_not_found(self, client, admin_token, admin_user):
        """Updating non-existent provider returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.put(
            f"/api/saml/providers/{fake_id}",
            json={"name": "Ghost"},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404

    def test_update_provider_viewer_forbidden(self, client, admin_token, admin_user, viewer_token, viewer_user):
        """Viewer cannot update providers."""
        create_resp = client.post(
            "/api/saml/providers",
            json=_create_saml_provider_payload(name="No Update"),
            headers=auth_header(admin_token),
        )
        provider_id = create_resp.json()["id"]

        response = client.put(
            f"/api/saml/providers/{provider_id}",
            json={"name": "Nope"},
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403


@pytest.mark.integration
class TestDeleteSAMLProvider:
    """Test DELETE /api/saml/providers/{id}"""

    def test_delete_provider(self, client, admin_token, admin_user):
        """Admin can delete a provider."""
        create_resp = client.post(
            "/api/saml/providers",
            json=_create_saml_provider_payload(name="Delete Me"),
            headers=auth_header(admin_token),
        )
        provider_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/saml/providers/{provider_id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 204

        # Confirm deletion
        response = client.get(
            f"/api/saml/providers/{provider_id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404

    def test_delete_provider_not_found(self, client, admin_token, admin_user):
        """Deleting non-existent provider returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.delete(
            f"/api/saml/providers/{fake_id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404

    def test_delete_provider_viewer_forbidden(self, client, admin_token, admin_user, viewer_token, viewer_user):
        """Viewer cannot delete providers."""
        create_resp = client.post(
            "/api/saml/providers",
            json=_create_saml_provider_payload(name="Keep Me"),
            headers=auth_header(admin_token),
        )
        provider_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/saml/providers/{provider_id}",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403


# ============================================================
#  SAML Metadata
# ============================================================

@pytest.mark.integration
class TestSAMLMetadata:
    """Test GET /api/saml/metadata"""

    def test_get_metadata(self, client):
        """SP metadata endpoint returns XML."""
        response = client.get("/api/saml/metadata")
        assert response.status_code == 200
        assert "xml" in response.headers.get("content-type", "").lower()
        body = response.text
        assert "EntityDescriptor" in body
        assert "SPSSODescriptor" in body


# ============================================================
#  SAML Login Flow
# ============================================================

@pytest.mark.integration
class TestSAMLLogin:
    """Test GET /api/saml/login/{provider_id}"""

    def test_login_with_valid_provider(self, client, admin_token, admin_user):
        """Initiate login with a configured provider returns redirect URL."""
        create_resp = client.post(
            "/api/saml/providers",
            json=_create_saml_provider_payload(name="Login IdP"),
            headers=auth_header(admin_token),
        )
        provider_id = create_resp.json()["id"]

        response = client.get(f"/api/saml/login/{provider_id}")
        assert response.status_code == 200
        data = response.json()
        assert "redirect_url" in data
        assert "request_id" in data
        assert "idp.example.com" in data["redirect_url"]

    def test_login_nonexistent_provider(self, client):
        """Login with unknown provider returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/saml/login/{fake_id}")
        assert response.status_code == 404


# ============================================================
#  SAML ACS (Assertion Consumer Service)
# ============================================================

@pytest.mark.integration
class TestSAMLACS:
    """Test POST /api/saml/acs"""

    def test_acs_invalid_response(self, client):
        """Invalid SAML response returns 401."""
        # Send a garbage base64 string as SAMLResponse
        import base64
        fake_response = base64.b64encode(b"<not-valid-saml/>").decode()

        response = client.post(
            "/api/saml/acs",
            data={"SAMLResponse": fake_response},
        )
        assert response.status_code == 401

    def test_acs_missing_saml_response(self, client):
        """Missing SAMLResponse field returns 422."""
        response = client.post("/api/saml/acs", data={})
        assert response.status_code == 422


# ============================================================
#  SAML SLO (Single Logout)
# ============================================================

@pytest.mark.integration
class TestSAMLSLO:
    """Test GET /api/saml/slo"""

    def test_slo_redirects(self, client):
        """SLO endpoint redirects to RelayState or root."""
        response = client.get(
            "/api/saml/slo?RelayState=https://app.example.com/dashboard",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "app.example.com/dashboard" in response.headers.get("location", "")

    def test_slo_default_redirect(self, client):
        """SLO without RelayState redirects to /."""
        response = client.get("/api/saml/slo", follow_redirects=False)
        assert response.status_code == 302
        location = response.headers.get("location", "")
        assert location.endswith("/")


# ============================================================
#  OAuth Providers endpoint
# ============================================================

@pytest.mark.integration
class TestOAuthProviders:
    """Test GET /api/auth/oauth/providers"""

    def test_get_providers(self, client):
        """Get OAuth providers response shape."""
        response = client.get("/api/auth/oauth/providers")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "providers" in data
        assert isinstance(data["providers"], list)


# ============================================================
#  OAuth Login
# ============================================================

@pytest.mark.integration
class TestOAuthLogin:
    """Test GET /api/auth/oauth/{provider}/login"""

    def test_login_invalid_provider(self, client):
        """Invalid provider name returns 400."""
        response = client.get(
            "/api/auth/oauth/invalid_provider/login",
            follow_redirects=False,
        )
        assert response.status_code == 400

    def test_login_unconfigured_provider(self, client):
        """Unconfigured but valid provider name returns 400."""
        # Google/Microsoft are valid enum values but likely not configured in test env
        response = client.get(
            "/api/auth/oauth/google/login",
            follow_redirects=False,
        )
        # Either 400 (not configured) or 307 redirect (if somehow configured)
        assert response.status_code in (400, 307, 302)


# ============================================================
#  OAuth Callback
# ============================================================

@pytest.mark.integration
class TestOAuthCallback:
    """Test GET /api/auth/oauth/{provider}/callback"""

    def test_callback_with_error(self, client):
        """Callback with error param returns 400."""
        response = client.get(
            "/api/auth/oauth/google/callback?error=access_denied&error_description=User+denied",
        )
        assert response.status_code == 400
        assert "access_denied" in response.json()["detail"].lower() or "denied" in response.json()["detail"].lower()

    def test_callback_no_code(self, client):
        """Callback without authorization code returns 400."""
        response = client.get(
            "/api/auth/oauth/google/callback?state=somestate",
        )
        assert response.status_code == 400

    def test_callback_invalid_state(self, client):
        """Callback with invalid state token returns 400."""
        response = client.get(
            "/api/auth/oauth/google/callback?code=fakecode&state=badstate",
        )
        assert response.status_code == 400
        assert "state" in response.json()["detail"].lower()

    def test_callback_invalid_provider(self, client):
        """Callback with invalid provider returns 400."""
        response = client.get(
            "/api/auth/oauth/notreal/callback?code=abc&state=xyz",
        )
        assert response.status_code == 400


# ============================================================
#  OAuth Token Exchange
# ============================================================

@pytest.mark.integration
class TestOAuthTokenExchange:
    """Test POST /api/auth/oauth/{provider}/token"""

    def test_token_exchange_invalid_provider(self, client):
        """Invalid provider returns 400."""
        response = client.post(
            "/api/auth/oauth/invalid/token?code=abc",
        )
        assert response.status_code == 400

    def test_token_exchange_unconfigured_provider(self, client):
        """Unconfigured provider returns 400."""
        response = client.post(
            "/api/auth/oauth/google/token?code=abc",
        )
        # Not configured -> 400, or if somehow configured -> 401 (code invalid)
        assert response.status_code in (400, 401)
