"""
OAuth API routes for SSO authentication.

Supports:
- Google OAuth 2.0
- Microsoft OAuth 2.0 (Azure AD)

Flow:
1. GET /auth/oauth/providers - Get list of configured providers
2. GET /auth/oauth/{provider}/login - Redirect to provider login
3. GET /auth/oauth/{provider}/callback - Handle provider callback
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.config import get_settings
from app.services.oauth_service import OAuthService, OAuthProvider, OAuthError
from app.services.auth_service import AuthService
from app.services.cache import get_cache

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/auth/oauth", tags=["OAuth"])

_OAUTH_STATE_TTL = 600  # 10 minutes


class OAuthProvidersResponse(BaseModel):
    """Available OAuth providers"""
    enabled: bool
    providers: List[str]


class OAuthTokenResponse(BaseModel):
    """OAuth login success response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


@router.get(
    "/providers",
    response_model=OAuthProvidersResponse,
    summary="Get available OAuth providers"
)
async def get_oauth_providers():
    """
    Get list of configured OAuth providers.

    Returns:
    - enabled: Whether OAuth is enabled
    - providers: List of configured provider names (google, microsoft)
    """
    return OAuthProvidersResponse(
        enabled=settings.oauth_enabled,
        providers=OAuthService.get_configured_providers()
    )


@router.get(
    "/{provider}/login",
    summary="Initiate OAuth login"
)
async def oauth_login(
    provider: str,
    redirect_url: Optional[str] = Query(
        default=None,
        description="URL to redirect to after successful login"
    ),
    db: Session = Depends(get_db)
):
    """
    Initiate OAuth login flow.

    Redirects user to the OAuth provider's login page.
    After authentication, user will be redirected back to the callback URL.

    **Providers:**
    - `google` - Google OAuth 2.0
    - `microsoft` - Microsoft/Azure AD OAuth 2.0

    **Query params:**
    - `redirect_url`: Optional URL to redirect to after login (for frontend integration)
    """
    try:
        oauth_provider = OAuthProvider(provider)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider: {provider}. Supported: google, microsoft"
        )

    if not OAuthService.is_provider_configured(oauth_provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider {provider} is not configured"
        )

    oauth_service = OAuthService(db)

    # Generate state token for CSRF protection
    state = oauth_service.generate_state_token()
    cache = get_cache()
    cache.set(f"oauth_state:{state}", redirect_url or "", ttl=_OAUTH_STATE_TTL)

    # Get auth URL and redirect
    auth_url = oauth_service.get_auth_url(oauth_provider, state)

    return RedirectResponse(url=auth_url)


@router.get(
    "/{provider}/callback",
    summary="OAuth callback handler"
)
async def oauth_callback(
    provider: str,
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    error_description: Optional[str] = Query(default=None),
    db: Session = Depends(get_db)
):
    """
    Handle OAuth provider callback.

    This endpoint is called by the OAuth provider after user authentication.
    It exchanges the authorization code for tokens and creates/finds the user.

    **On success:** Returns JWT tokens or redirects to frontend with tokens.
    **On failure:** Returns error details.
    """
    # Handle provider errors
    if error:
        logger.warning(f"OAuth error from {provider}: {error} - {error_description}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth error: {error_description or error}"
        )

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No authorization code received"
        )

    # Validate state (CSRF protection)
    cache = get_cache()
    state_key = f"oauth_state:{state}"
    redirect_url = cache.get(state_key) if state else None
    if not state or redirect_url is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state token"
        )

    cache.delete(state_key)

    try:
        oauth_provider = OAuthProvider(provider)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider: {provider}"
        )

    oauth_service = OAuthService(db)

    try:
        user, access_token, refresh_token = await oauth_service.authenticate(
            oauth_provider,
            code,
            auto_create_user=True
        )

        # Store refresh token
        AuthService.store_refresh_token(
            db,
            str(user.id),
            refresh_token,
            user_agent=f"OAuth/{provider}",
            ip_address=None
        )

        # If redirect_url provided, redirect with tokens in query params
        if redirect_url:
            return RedirectResponse(
                url=f"{redirect_url}?access_token={access_token}&refresh_token={refresh_token}"
            )

        # Otherwise return JSON response
        return OAuthTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60,
            user={
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "role": user.role.value,
            }
        )

    except OAuthError as e:
        logger.error(f"OAuth authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Unexpected OAuth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth authentication failed"
        )


@router.post(
    "/{provider}/token",
    response_model=OAuthTokenResponse,
    summary="Exchange OAuth code for tokens (API mode)"
)
async def oauth_token_exchange(
    provider: str,
    code: str = Query(..., description="Authorization code from OAuth provider"),
    db: Session = Depends(get_db)
):
    """
    Exchange OAuth authorization code for JWT tokens.

    This endpoint is for API-based OAuth flows where the frontend handles
    the OAuth redirect and sends the authorization code to this endpoint.

    **Usage:**
    1. Frontend redirects user to OAuth provider
    2. Provider redirects back to frontend with code
    3. Frontend calls this endpoint with the code
    4. Backend exchanges code and returns JWT tokens
    """
    try:
        oauth_provider = OAuthProvider(provider)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider: {provider}. Supported: google, microsoft"
        )

    if not OAuthService.is_provider_configured(oauth_provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider {provider} is not configured"
        )

    oauth_service = OAuthService(db)

    try:
        user, access_token, refresh_token = await oauth_service.authenticate(
            oauth_provider,
            code,
            auto_create_user=True
        )

        # Store refresh token
        AuthService.store_refresh_token(
            db,
            str(user.id),
            refresh_token,
            user_agent=f"OAuth/{provider}",
            ip_address=None
        )

        return OAuthTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60,
            user={
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "role": user.role.value,
            }
        )

    except OAuthError as e:
        logger.error(f"OAuth token exchange failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
