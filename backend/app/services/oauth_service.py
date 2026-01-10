"""
OAuth Service for SSO Authentication.

Supports:
- Google OAuth 2.0
- Microsoft OAuth 2.0 (Azure AD)

OAuth Flow:
1. Generate auth URL -> redirect user to provider
2. Provider redirects back with code
3. Exchange code for tokens
4. Get user info from provider
5. Create/update local user
6. Generate JWT tokens
"""

import logging
import secrets
import httpx
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User, UserRole
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)
settings = get_settings()


class OAuthProvider(str, Enum):
    """Supported OAuth providers"""
    GOOGLE = "google"
    MICROSOFT = "microsoft"


@dataclass
class OAuthUserInfo:
    """User information from OAuth provider"""
    email: str
    name: Optional[str]
    given_name: Optional[str]
    family_name: Optional[str]
    picture_url: Optional[str]
    provider: OAuthProvider
    provider_user_id: str


class OAuthError(Exception):
    """OAuth authentication error"""
    pass


class OAuthService:
    """
    Service for OAuth authentication with Google and Microsoft.
    """

    # OAuth endpoints
    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

    MICROSOFT_AUTH_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
    MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    MICROSOFT_USERINFO_URL = "https://graph.microsoft.com/v1.0/me"

    def __init__(self, db: Session):
        self.db = db
        self._state_tokens: Dict[str, str] = {}  # In production, use Redis

    @staticmethod
    def is_provider_configured(provider: OAuthProvider) -> bool:
        """Check if an OAuth provider is configured"""
        if not settings.oauth_enabled:
            return False

        if provider == OAuthProvider.GOOGLE:
            return bool(settings.google_client_id and settings.google_client_secret)
        elif provider == OAuthProvider.MICROSOFT:
            return bool(settings.microsoft_client_id and settings.microsoft_client_secret)
        return False

    @staticmethod
    def get_configured_providers() -> list:
        """Get list of configured OAuth providers"""
        providers = []
        if settings.oauth_enabled:
            if settings.google_client_id and settings.google_client_secret:
                providers.append("google")
            if settings.microsoft_client_id and settings.microsoft_client_secret:
                providers.append("microsoft")
        return providers

    def generate_state_token(self) -> str:
        """Generate CSRF protection state token"""
        return secrets.token_urlsafe(32)

    def get_auth_url(self, provider: OAuthProvider, state: str) -> str:
        """
        Get OAuth authorization URL for provider.

        Args:
            provider: OAuth provider
            state: CSRF state token

        Returns:
            Authorization URL to redirect user to
        """
        redirect_uri = f"{settings.oauth_base_url}/auth/oauth/{provider.value}/callback"

        if provider == OAuthProvider.GOOGLE:
            params = {
                "client_id": settings.google_client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "access_type": "offline",
                "prompt": "select_account",
            }
            return f"{self.GOOGLE_AUTH_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

        elif provider == OAuthProvider.MICROSOFT:
            auth_url = self.MICROSOFT_AUTH_URL.format(tenant=settings.microsoft_tenant_id)
            params = {
                "client_id": settings.microsoft_client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile User.Read",
                "state": state,
                "response_mode": "query",
            }
            return f"{auth_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

        raise OAuthError(f"Unsupported provider: {provider}")

    async def exchange_code_for_tokens(
        self,
        provider: OAuthProvider,
        code: str
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access tokens.

        Args:
            provider: OAuth provider
            code: Authorization code from callback

        Returns:
            Token response dict with access_token, etc.
        """
        redirect_uri = f"{settings.oauth_base_url}/auth/oauth/{provider.value}/callback"

        async with httpx.AsyncClient() as client:
            if provider == OAuthProvider.GOOGLE:
                response = await client.post(
                    self.GOOGLE_TOKEN_URL,
                    data={
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                    },
                )

            elif provider == OAuthProvider.MICROSOFT:
                token_url = self.MICROSOFT_TOKEN_URL.format(
                    tenant=settings.microsoft_tenant_id
                )
                response = await client.post(
                    token_url,
                    data={
                        "client_id": settings.microsoft_client_id,
                        "client_secret": settings.microsoft_client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                        "scope": "openid email profile User.Read",
                    },
                )
            else:
                raise OAuthError(f"Unsupported provider: {provider}")

            if response.status_code != 200:
                logger.error(f"Token exchange failed: {response.text}")
                raise OAuthError(f"Failed to exchange code for tokens: {response.text}")

            return response.json()

    async def get_user_info(
        self,
        provider: OAuthProvider,
        access_token: str
    ) -> OAuthUserInfo:
        """
        Get user information from OAuth provider.

        Args:
            provider: OAuth provider
            access_token: Access token from token exchange

        Returns:
            OAuthUserInfo with user details
        """
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            if provider == OAuthProvider.GOOGLE:
                response = await client.get(
                    self.GOOGLE_USERINFO_URL,
                    headers=headers
                )
                if response.status_code != 200:
                    raise OAuthError(f"Failed to get user info: {response.text}")

                data = response.json()
                return OAuthUserInfo(
                    email=data.get("email"),
                    name=data.get("name"),
                    given_name=data.get("given_name"),
                    family_name=data.get("family_name"),
                    picture_url=data.get("picture"),
                    provider=OAuthProvider.GOOGLE,
                    provider_user_id=data.get("sub"),
                )

            elif provider == OAuthProvider.MICROSOFT:
                response = await client.get(
                    self.MICROSOFT_USERINFO_URL,
                    headers=headers
                )
                if response.status_code != 200:
                    raise OAuthError(f"Failed to get user info: {response.text}")

                data = response.json()
                return OAuthUserInfo(
                    email=data.get("mail") or data.get("userPrincipalName"),
                    name=data.get("displayName"),
                    given_name=data.get("givenName"),
                    family_name=data.get("surname"),
                    picture_url=None,  # Microsoft Graph requires separate call for photo
                    provider=OAuthProvider.MICROSOFT,
                    provider_user_id=data.get("id"),
                )

            raise OAuthError(f"Unsupported provider: {provider}")

    def find_or_create_user(
        self,
        user_info: OAuthUserInfo,
        auto_create: bool = True
    ) -> Optional[User]:
        """
        Find existing user or create new one from OAuth info.

        Args:
            user_info: OAuth user information
            auto_create: Whether to create new user if not found

        Returns:
            User object or None if not found and auto_create=False
        """
        # Try to find by email
        user = self.db.query(User).filter(
            User.email == user_info.email
        ).first()

        if user:
            # Update last login
            user.last_login = datetime.utcnow()
            self.db.commit()
            return user

        if not auto_create:
            return None

        # Create new user from OAuth info
        # Generate username from email
        username = user_info.email.split("@")[0]

        # Ensure username is unique
        base_username = username
        counter = 1
        while self.db.query(User).filter(User.username == username).first():
            username = f"{base_username}{counter}"
            counter += 1

        # Create user with random password (they'll use OAuth to login)
        random_password = secrets.token_urlsafe(32)

        user = User(
            username=username,
            email=user_info.email,
            hashed_password=AuthService.hash_password(random_password),
            role=UserRole.VIEWER,  # Default role for OAuth users
            is_active=True,
            is_locked=False,
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow(),
        )

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        logger.info(
            f"Created new OAuth user: {user.username} ({user.email}) "
            f"via {user_info.provider.value}"
        )

        return user

    async def authenticate(
        self,
        provider: OAuthProvider,
        code: str,
        auto_create_user: bool = True
    ) -> Tuple[User, str, str]:
        """
        Full OAuth authentication flow.

        Args:
            provider: OAuth provider
            code: Authorization code from callback
            auto_create_user: Whether to create new users

        Returns:
            Tuple of (user, access_token, refresh_token)

        Raises:
            OAuthError: If authentication fails
        """
        # Exchange code for tokens
        tokens = await self.exchange_code_for_tokens(provider, code)
        access_token = tokens.get("access_token")

        if not access_token:
            raise OAuthError("No access token received")

        # Get user info
        user_info = await self.get_user_info(provider, access_token)

        if not user_info.email:
            raise OAuthError("Email not provided by OAuth provider")

        # Find or create user
        user = self.find_or_create_user(user_info, auto_create=auto_create_user)

        if not user:
            raise OAuthError("User not found and auto-create is disabled")

        if not user.is_active:
            raise OAuthError("User account is inactive")

        if user.is_locked:
            raise OAuthError("User account is locked")

        # Generate JWT tokens
        jwt_access, jwt_refresh = AuthService.create_token_pair(user)

        return user, jwt_access, jwt_refresh
