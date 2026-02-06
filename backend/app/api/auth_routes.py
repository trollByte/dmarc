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
from app.models import User, UserRole
from app.config import get_settings
from app.services.auth_service import AuthService
from app.services.password_reset_service import PasswordResetService, PasswordResetError
from app.services.totp_service import TOTPService
from app.dependencies.auth import get_current_user
from app.schemas.auth_schemas import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    AccessTokenResponse,
    CurrentUserContext,
    PasswordResetRequest,
    PasswordResetValidate,
    PasswordResetConfirm,
    PasswordResetResponse,
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

    # Check 2FA if enabled
    if user.totp_enabled:
        totp_service = TOTPService(db)

        # Check if TOTP code provided
        if credentials.totp_code:
            if not totp_service.verify_code(user, credentials.totp_code):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid two-factor authentication code"
                )
        # Check if backup code provided
        elif credentials.backup_code:
            if not totp_service.verify_backup_code(user, credentials.backup_code):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid backup code"
                )
        else:
            # Return a response indicating 2FA is required
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Two-factor authentication required",
                headers={"X-2FA-Required": "true"}
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
    role = user.role if isinstance(user.role, UserRole) else UserRole(user.role)
    access_token = AuthService.create_access_token(
        str(user.id),
        user.username,
        role
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


# ==================== Password Reset Endpoints ====================

@router.post(
    "/password-reset/request",
    response_model=PasswordResetResponse,
    status_code=status.HTTP_200_OK,
    summary="Request password reset"
)
async def request_password_reset(
    request: Request,
    reset_request: PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """
    Request a password reset email.

    **Security Notes:**
    - Always returns success to prevent email enumeration
    - Reset link expires in 1 hour
    - Only one active reset token per user

    **Usage:**
    ```
    POST /auth/password-reset/request
    {
        "email": "user@example.com"
    }
    ```

    **Response:**
    ```json
    {
        "success": true,
        "message": "If an account exists with this email, a reset link has been sent."
    }
    ```
    """
    client_ip = request.client.host if request.client else None

    service = PasswordResetService(db)
    success, token = service.request_reset(
        email=reset_request.email,
        request_ip=client_ip
    )

    # If we have a token, send reset email
    if token:
        # In production, this would send a real email
        reset_url_base = f"{settings.frontend_url}/reset-password"
        service.send_reset_email(
            email=reset_request.email,
            reset_token=token,
            reset_url_base=reset_url_base
        )

    # Always return same message to prevent email enumeration
    return PasswordResetResponse(
        success=True,
        message="If an account exists with this email, a reset link has been sent."
    )


@router.post(
    "/password-reset/validate",
    response_model=PasswordResetResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate password reset token"
)
async def validate_reset_token(
    validate_request: PasswordResetValidate,
    db: Session = Depends(get_db)
):
    """
    Validate a password reset token.

    **Usage:**
    ```
    POST /auth/password-reset/validate
    {
        "token": "<reset_token_from_email>"
    }
    ```

    **Response:**
    - 200: Token is valid
    - 400: Token is invalid or expired
    """
    service = PasswordResetService(db)
    user = service.validate_token(validate_request.token)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    return PasswordResetResponse(
        success=True,
        message="Token is valid"
    )


@router.post(
    "/password-reset/confirm",
    response_model=PasswordResetResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset password with token"
)
async def confirm_password_reset(
    confirm_request: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """
    Reset password using the reset token.

    **Password Requirements:**
    - Minimum 12 characters
    - Must contain uppercase letter
    - Must contain lowercase letter
    - Must contain digit
    - Must contain special character

    **Usage:**
    ```
    POST /auth/password-reset/confirm
    {
        "token": "<reset_token_from_email>",
        "new_password": "NewSecurePassword123!"
    }
    ```

    **What happens:**
    - Password is updated
    - Account is unlocked (if locked)
    - All existing sessions are invalidated
    - User must login with new password

    **Response:**
    - 200: Password reset successful
    - 400: Invalid token or password policy violation
    """
    service = PasswordResetService(db)

    try:
        service.reset_password(
            token=confirm_request.token,
            new_password=confirm_request.new_password
        )
    except PasswordResetError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return PasswordResetResponse(
        success=True,
        message="Password has been reset successfully. Please login with your new password."
    )
