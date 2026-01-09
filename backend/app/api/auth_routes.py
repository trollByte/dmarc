"""
Authentication API routes.

Endpoints:
- POST /auth/login - Login with username/password
- POST /auth/refresh - Refresh access token
- POST /auth/logout - Logout (revoke refresh token)
- POST /auth/logout/all - Logout all sessions
- GET /auth/me - Get current user info
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.config import get_settings
from app.services.auth_service import AuthService
from app.dependencies.auth import get_current_user
from app.schemas.auth_schemas import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    AccessTokenResponse,
    CurrentUserContext,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login with username and password"
)
async def login(
    request: Request,
    credentials: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT access + refresh tokens.

    **Authentication Flow:**
    1. User provides username (or email) and password
    2. System validates credentials
    3. Returns access token (15min) + refresh token (7 days)

    **Usage:**
    ```
    POST /auth/login
    {
        "username": "admin",
        "password": "SecurePassword123!"
    }
    ```

    **Response:**
    - **access_token**: Use in Authorization header: `Bearer <token>`
    - **refresh_token**: Use to get new access token when expired
    - **expires_in**: Seconds until access token expires (900 = 15 minutes)

    **Errors:**
    - 401: Invalid credentials
    - 403: Account inactive or locked
    """
    # Authenticate user
    user = AuthService.authenticate_user(db, credentials.username, credentials.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )

    if user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is locked due to too many failed login attempts. Contact administrator."
        )

    # Create token pair
    access_token, refresh_token = AuthService.create_token_pair(user)

    # Store refresh token in database
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    AuthService.store_refresh_token(
        db,
        str(user.id),
        refresh_token,
        user_agent=user_agent,
        ip_address=client_ip
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60
    )


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token"
)
async def refresh_token(
    refresh_request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Get new access token using refresh token.

    **When to use:**
    - When access token expires (401 error with "token expired" message)
    - Proactively before access token expires

    **Usage:**
    ```
    POST /auth/refresh
    {
        "refresh_token": "<refresh_token>"
    }
    ```

    **Response:**
    - **access_token**: New JWT access token (15min)
    - **expires_in**: Seconds until expiration

    **Errors:**
    - 401: Invalid, expired, or revoked refresh token
    """
    # Validate refresh token and get user
    user = AuthService.validate_refresh_token(db, refresh_request.refresh_token)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    # Create new access token
    access_token = AuthService.create_access_token(
        str(user.id),
        user.username,
        user.role
    )

    return AccessTokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout (revoke refresh token)"
)
async def logout(
    refresh_request: RefreshTokenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Logout user by revoking refresh token.

    **What happens:**
    - Revokes the provided refresh token
    - Access token remains valid until expiration (max 15min)
    - User must login again to get new tokens

    **Usage:**
    ```
    POST /auth/logout
    Authorization: Bearer <access_token>
    {
        "refresh_token": "<refresh_token>"
    }
    ```

    **Response:**
    ```json
    {
        "message": "Logged out successfully"
    }
    ```
    """
    success = AuthService.revoke_refresh_token(db, refresh_request.refresh_token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Refresh token not found"
        )

    return {"message": "Logged out successfully"}


@router.post(
    "/logout/all",
    status_code=status.HTTP_200_OK,
    summary="Logout all sessions"
)
async def logout_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Logout user from all devices/sessions.

    **What happens:**
    - Revokes ALL refresh tokens for current user
    - All active sessions will need to re-authenticate
    - Access tokens remain valid until expiration (max 15min)

    **Usage:**
    ```
    POST /auth/logout/all
    Authorization: Bearer <access_token>
    ```

    **Response:**
    ```json
    {
        "message": "Logged out from 3 sessions"
    }
    ```
    """
    count = AuthService.revoke_all_user_tokens(db, str(current_user.id))

    return {
        "message": f"Logged out from {count} session{'s' if count != 1 else ''}"
    }


@router.get(
    "/me",
    response_model=CurrentUserContext,
    status_code=status.HTTP_200_OK,
    summary="Get current user info"
)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get information about the currently authenticated user.

    **Returns:**
    - User profile (id, username, email, role)
    - Permissions based on role
    - Account status

    **Usage:**
    ```
    GET /auth/me
    Authorization: Bearer <access_token>
    ```

    **Response:**
    ```json
    {
        "user": {
            "id": "uuid",
            "username": "admin",
            "email": "admin@example.com",
            "role": "admin",
            "is_active": true,
            "is_locked": false,
            "created_at": "2024-01-01T00:00:00",
            "last_login": "2024-01-09T14:00:00"
        },
        "permissions": [
            "users:create", "users:read", "users:update", ...
        ]
    }
    ```
    """
    return CurrentUserContext.from_user(current_user)
