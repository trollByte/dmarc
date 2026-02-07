"""Unit tests for OAuthService (oauth_service.py)"""
import pytest
import uuid
import secrets
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch, AsyncMock

from app.services.oauth_service import (
    OAuthService,
    OAuthProvider,
    OAuthUserInfo,
    OAuthError,
)


@pytest.mark.unit
class TestProviderConfiguration:
    """Test OAuth provider configuration checks"""

    @patch("app.services.oauth_service.settings")
    def test_google_configured(self, mock_settings):
        """Test Google provider is reported as configured"""
        mock_settings.oauth_enabled = True
        mock_settings.google_client_id = "google-client-id"
        mock_settings.google_client_secret = "google-client-secret"

        assert OAuthService.is_provider_configured(OAuthProvider.GOOGLE) is True

    @patch("app.services.oauth_service.settings")
    def test_google_not_configured(self, mock_settings):
        """Test Google provider not configured when missing credentials"""
        mock_settings.oauth_enabled = True
        mock_settings.google_client_id = None
        mock_settings.google_client_secret = None

        assert OAuthService.is_provider_configured(OAuthProvider.GOOGLE) is False

    @patch("app.services.oauth_service.settings")
    def test_microsoft_configured(self, mock_settings):
        """Test Microsoft provider is reported as configured"""
        mock_settings.oauth_enabled = True
        mock_settings.microsoft_client_id = "ms-client-id"
        mock_settings.microsoft_client_secret = "ms-client-secret"

        assert OAuthService.is_provider_configured(OAuthProvider.MICROSOFT) is True

    @patch("app.services.oauth_service.settings")
    def test_microsoft_not_configured(self, mock_settings):
        """Test Microsoft provider not configured when missing credentials"""
        mock_settings.oauth_enabled = True
        mock_settings.microsoft_client_id = None
        mock_settings.microsoft_client_secret = None

        assert OAuthService.is_provider_configured(OAuthProvider.MICROSOFT) is False

    @patch("app.services.oauth_service.settings")
    def test_oauth_disabled(self, mock_settings):
        """Test all providers report not configured when OAuth disabled"""
        mock_settings.oauth_enabled = False
        mock_settings.google_client_id = "google-client-id"
        mock_settings.google_client_secret = "google-client-secret"

        assert OAuthService.is_provider_configured(OAuthProvider.GOOGLE) is False
        assert OAuthService.is_provider_configured(OAuthProvider.MICROSOFT) is False

    @patch("app.services.oauth_service.settings")
    def test_get_configured_providers_both(self, mock_settings):
        """Test getting list of configured providers"""
        mock_settings.oauth_enabled = True
        mock_settings.google_client_id = "gid"
        mock_settings.google_client_secret = "gsecret"
        mock_settings.microsoft_client_id = "mid"
        mock_settings.microsoft_client_secret = "msecret"

        providers = OAuthService.get_configured_providers()

        assert "google" in providers
        assert "microsoft" in providers

    @patch("app.services.oauth_service.settings")
    def test_get_configured_providers_none(self, mock_settings):
        """Test getting configured providers when none are configured"""
        mock_settings.oauth_enabled = False

        providers = OAuthService.get_configured_providers()

        assert len(providers) == 0


@pytest.mark.unit
class TestAuthURL:
    """Test OAuth authorization URL generation"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return OAuthService(mock_db)

    @patch("app.services.oauth_service.settings")
    def test_google_auth_url(self, mock_settings, service):
        """Test Google OAuth authorization URL generation"""
        mock_settings.google_client_id = "test-google-client-id"
        mock_settings.oauth_base_url = "https://dmarc.example.com"

        state = "test-state-token"
        url = service.get_auth_url(OAuthProvider.GOOGLE, state)

        assert "accounts.google.com" in url
        assert "test-google-client-id" in url
        assert "test-state-token" in url
        assert "openid" in url
        assert "email" in url
        assert "profile" in url

    @patch("app.services.oauth_service.settings")
    def test_microsoft_auth_url(self, mock_settings, service):
        """Test Microsoft OAuth authorization URL generation"""
        mock_settings.microsoft_client_id = "test-ms-client-id"
        mock_settings.microsoft_tenant_id = "test-tenant-id"
        mock_settings.oauth_base_url = "https://dmarc.example.com"

        state = "test-state-token"
        url = service.get_auth_url(OAuthProvider.MICROSOFT, state)

        assert "login.microsoftonline.com" in url
        assert "test-tenant-id" in url
        assert "test-ms-client-id" in url
        assert "test-state-token" in url

    def test_generate_state_token(self, service):
        """Test state token generation produces unique tokens"""
        token1 = service.generate_state_token()
        token2 = service.generate_state_token()

        assert isinstance(token1, str)
        assert len(token1) > 20
        assert token1 != token2


@pytest.mark.unit
class TestTokenExchange:
    """Test OAuth code-for-token exchange"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return OAuthService(mock_db)

    @pytest.mark.asyncio
    @patch("app.services.oauth_service.settings")
    async def test_exchange_code_google_success(self, mock_settings, service):
        """Test successful Google token exchange"""
        mock_settings.google_client_id = "google-id"
        mock_settings.google_client_secret = "google-secret"
        mock_settings.oauth_base_url = "https://dmarc.example.com"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "google-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        with patch("app.services.oauth_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await service.exchange_code_for_tokens(
                OAuthProvider.GOOGLE, "auth-code-123"
            )

        assert result["access_token"] == "google-access-token"

    @pytest.mark.asyncio
    @patch("app.services.oauth_service.settings")
    async def test_exchange_code_microsoft_success(self, mock_settings, service):
        """Test successful Microsoft token exchange"""
        mock_settings.microsoft_client_id = "ms-id"
        mock_settings.microsoft_client_secret = "ms-secret"
        mock_settings.microsoft_tenant_id = "ms-tenant"
        mock_settings.oauth_base_url = "https://dmarc.example.com"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "ms-access-token",
            "token_type": "Bearer",
        }

        with patch("app.services.oauth_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await service.exchange_code_for_tokens(
                OAuthProvider.MICROSOFT, "ms-auth-code"
            )

        assert result["access_token"] == "ms-access-token"

    @pytest.mark.asyncio
    @patch("app.services.oauth_service.settings")
    async def test_exchange_code_failure(self, mock_settings, service):
        """Test token exchange failure raises OAuthError"""
        mock_settings.google_client_id = "google-id"
        mock_settings.google_client_secret = "google-secret"
        mock_settings.oauth_base_url = "https://dmarc.example.com"

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "invalid_grant"

        with patch("app.services.oauth_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            with pytest.raises(OAuthError, match="Failed to exchange code"):
                await service.exchange_code_for_tokens(
                    OAuthProvider.GOOGLE, "bad-code"
                )


@pytest.mark.unit
class TestGetUserInfo:
    """Test getting user info from OAuth providers"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return OAuthService(mock_db)

    @pytest.mark.asyncio
    async def test_get_user_info_google(self, service):
        """Test getting user info from Google"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "email": "user@gmail.com",
            "name": "John Doe",
            "given_name": "John",
            "family_name": "Doe",
            "picture": "https://photos.example.com/photo.jpg",
            "sub": "google-user-id-123",
        }

        with patch("app.services.oauth_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await service.get_user_info(OAuthProvider.GOOGLE, "access-token")

        assert isinstance(result, OAuthUserInfo)
        assert result.email == "user@gmail.com"
        assert result.name == "John Doe"
        assert result.provider == OAuthProvider.GOOGLE
        assert result.provider_user_id == "google-user-id-123"
        assert result.picture_url == "https://photos.example.com/photo.jpg"

    @pytest.mark.asyncio
    async def test_get_user_info_microsoft(self, service):
        """Test getting user info from Microsoft"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "mail": "user@outlook.com",
            "displayName": "Jane Smith",
            "givenName": "Jane",
            "surname": "Smith",
            "id": "ms-user-id-456",
        }

        with patch("app.services.oauth_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await service.get_user_info(OAuthProvider.MICROSOFT, "ms-token")

        assert result.email == "user@outlook.com"
        assert result.name == "Jane Smith"
        assert result.provider == OAuthProvider.MICROSOFT
        assert result.picture_url is None  # Microsoft requires separate call

    @pytest.mark.asyncio
    async def test_get_user_info_microsoft_fallback_email(self, service):
        """Test Microsoft falls back to userPrincipalName when mail is None"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "mail": None,
            "userPrincipalName": "user@contoso.onmicrosoft.com",
            "displayName": "Test User",
            "id": "ms-id",
        }

        with patch("app.services.oauth_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await service.get_user_info(OAuthProvider.MICROSOFT, "ms-token")

        assert result.email == "user@contoso.onmicrosoft.com"

    @pytest.mark.asyncio
    async def test_get_user_info_failure(self, service):
        """Test user info retrieval failure raises OAuthError"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("app.services.oauth_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)

            with pytest.raises(OAuthError, match="Failed to get user info"):
                await service.get_user_info(OAuthProvider.GOOGLE, "bad-token")


@pytest.mark.unit
class TestFindOrCreateUser:
    """Test user lookup and creation from OAuth info"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return OAuthService(mock_db)

    def test_find_existing_user(self, service, mock_db):
        """Test finding an existing user by email"""
        existing_user = Mock()
        existing_user.email = "user@example.com"
        existing_user.last_login = None
        mock_db.query.return_value.filter.return_value.first.return_value = existing_user

        user_info = OAuthUserInfo(
            email="user@example.com",
            name="Test User",
            given_name="Test",
            family_name="User",
            picture_url=None,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-123",
        )

        result = service.find_or_create_user(user_info)

        assert result is existing_user
        assert existing_user.last_login is not None
        assert mock_db.commit.called

    def test_create_new_user(self, service, mock_db):
        """Test creating a new user when not found"""
        # First call returns None (user not found by email)
        # Second call returns None (username not taken)
        mock_db.query.return_value.filter.return_value.first.side_effect = [None, None]

        user_info = OAuthUserInfo(
            email="newuser@example.com",
            name="New User",
            given_name="New",
            family_name="User",
            picture_url=None,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-456",
        )

        with patch("app.services.oauth_service.AuthService.hash_password", return_value="hashed"):
            result = service.find_or_create_user(user_info)

        assert mock_db.add.called
        assert mock_db.commit.called
        assert mock_db.refresh.called

        added_user = mock_db.add.call_args[0][0]
        assert added_user.email == "newuser@example.com"
        assert added_user.username == "newuser"
        assert added_user.is_active is True

    def test_no_auto_create(self, service, mock_db):
        """Test returns None when user not found and auto_create=False"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        user_info = OAuthUserInfo(
            email="unknown@example.com",
            name="Unknown",
            given_name="Un",
            family_name="Known",
            picture_url=None,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-789",
        )

        result = service.find_or_create_user(user_info, auto_create=False)

        assert result is None

    def test_create_user_unique_username(self, service, mock_db):
        """Test username deduplication when base username is taken"""
        # First call: email lookup returns None (no existing user)
        # Second call: username 'user' is taken
        # Third call: username 'user1' is free
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            None,       # email lookup
            Mock(),     # username 'user' taken
            None,       # username 'user1' free
        ]

        user_info = OAuthUserInfo(
            email="user@example.com",
            name="User",
            given_name="User",
            family_name="Test",
            picture_url=None,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-111",
        )

        with patch("app.services.oauth_service.AuthService.hash_password", return_value="hashed"):
            result = service.find_or_create_user(user_info)

        added_user = mock_db.add.call_args[0][0]
        assert added_user.username == "user1"


@pytest.mark.unit
class TestFullAuthentication:
    """Test full OAuth authentication flow"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return OAuthService(mock_db)

    @pytest.mark.asyncio
    async def test_authenticate_success(self, service):
        """Test full authentication flow succeeds"""
        mock_user = Mock()
        mock_user.id = uuid.uuid4()
        mock_user.is_active = True
        mock_user.is_locked = False

        with patch.object(
            service, 'exchange_code_for_tokens',
            new_callable=AsyncMock,
            return_value={"access_token": "test-token"}
        ):
            with patch.object(
                service, 'get_user_info',
                new_callable=AsyncMock,
                return_value=OAuthUserInfo(
                    email="user@example.com",
                    name="User",
                    given_name="User",
                    family_name="Test",
                    picture_url=None,
                    provider=OAuthProvider.GOOGLE,
                    provider_user_id="g-123",
                )
            ):
                with patch.object(service, 'find_or_create_user', return_value=mock_user):
                    with patch(
                        "app.services.oauth_service.AuthService.create_token_pair",
                        return_value=("jwt-access", "jwt-refresh")
                    ):
                        user, access, refresh = await service.authenticate(
                            OAuthProvider.GOOGLE, "auth-code"
                        )

        assert user is mock_user
        assert access == "jwt-access"
        assert refresh == "jwt-refresh"

    @pytest.mark.asyncio
    async def test_authenticate_no_access_token(self, service):
        """Test authentication fails when no access token received"""
        with patch.object(
            service, 'exchange_code_for_tokens',
            new_callable=AsyncMock,
            return_value={"error": "invalid_grant"}
        ):
            with pytest.raises(OAuthError, match="No access token"):
                await service.authenticate(OAuthProvider.GOOGLE, "bad-code")

    @pytest.mark.asyncio
    async def test_authenticate_no_email(self, service):
        """Test authentication fails when email not provided"""
        with patch.object(
            service, 'exchange_code_for_tokens',
            new_callable=AsyncMock,
            return_value={"access_token": "token"}
        ):
            with patch.object(
                service, 'get_user_info',
                new_callable=AsyncMock,
                return_value=OAuthUserInfo(
                    email=None,
                    name="No Email",
                    given_name=None,
                    family_name=None,
                    picture_url=None,
                    provider=OAuthProvider.GOOGLE,
                    provider_user_id="g-999",
                )
            ):
                with pytest.raises(OAuthError, match="Email not provided"):
                    await service.authenticate(OAuthProvider.GOOGLE, "code")

    @pytest.mark.asyncio
    async def test_authenticate_user_inactive(self, service):
        """Test authentication fails for inactive user"""
        mock_user = Mock()
        mock_user.is_active = False
        mock_user.is_locked = False

        with patch.object(
            service, 'exchange_code_for_tokens',
            new_callable=AsyncMock,
            return_value={"access_token": "token"}
        ):
            with patch.object(
                service, 'get_user_info',
                new_callable=AsyncMock,
                return_value=OAuthUserInfo(
                    email="user@example.com",
                    name="Inactive",
                    given_name=None,
                    family_name=None,
                    picture_url=None,
                    provider=OAuthProvider.GOOGLE,
                    provider_user_id="g-inactive",
                )
            ):
                with patch.object(service, 'find_or_create_user', return_value=mock_user):
                    with pytest.raises(OAuthError, match="inactive"):
                        await service.authenticate(OAuthProvider.GOOGLE, "code")

    @pytest.mark.asyncio
    async def test_authenticate_user_locked(self, service):
        """Test authentication fails for locked user"""
        mock_user = Mock()
        mock_user.is_active = True
        mock_user.is_locked = True

        with patch.object(
            service, 'exchange_code_for_tokens',
            new_callable=AsyncMock,
            return_value={"access_token": "token"}
        ):
            with patch.object(
                service, 'get_user_info',
                new_callable=AsyncMock,
                return_value=OAuthUserInfo(
                    email="user@example.com",
                    name="Locked",
                    given_name=None,
                    family_name=None,
                    picture_url=None,
                    provider=OAuthProvider.GOOGLE,
                    provider_user_id="g-locked",
                )
            ):
                with patch.object(service, 'find_or_create_user', return_value=mock_user):
                    with pytest.raises(OAuthError, match="locked"):
                        await service.authenticate(OAuthProvider.GOOGLE, "code")

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found_no_autocreate(self, service):
        """Test authentication fails when user not found and auto_create disabled"""
        with patch.object(
            service, 'exchange_code_for_tokens',
            new_callable=AsyncMock,
            return_value={"access_token": "token"}
        ):
            with patch.object(
                service, 'get_user_info',
                new_callable=AsyncMock,
                return_value=OAuthUserInfo(
                    email="nope@example.com",
                    name="Nope",
                    given_name=None,
                    family_name=None,
                    picture_url=None,
                    provider=OAuthProvider.GOOGLE,
                    provider_user_id="g-nope",
                )
            ):
                with patch.object(service, 'find_or_create_user', return_value=None):
                    with pytest.raises(OAuthError, match="not found"):
                        await service.authenticate(
                            OAuthProvider.GOOGLE, "code", auto_create_user=False
                        )
