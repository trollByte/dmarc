"""
Pydantic schemas for authentication and user management.
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime
from uuid import UUID

from app.models import UserRole


# ==================== Authentication Schemas ====================

class LoginRequest(BaseModel):
    """Login request with username/email and password"""
    username: str = Field(..., description="Username or email address")
    password: str = Field(..., description="Password")
    totp_code: Optional[str] = Field(None, min_length=6, max_length=6, description="6-digit TOTP code (if 2FA enabled)")
    backup_code: Optional[str] = Field(None, description="Backup code (if 2FA enabled, format: XXXX-XXXX)")


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str = Field(..., description="JWT access token (15min)")
    refresh_token: str = Field(..., description="JWT refresh token (7 days)")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")
    requires_2fa: bool = Field(default=False, description="Whether 2FA verification is required")


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str = Field(..., description="JWT refresh token")


class AccessTokenResponse(BaseModel):
    """New access token response"""
    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")


# ==================== User Schemas ====================

class UserBase(BaseModel):
    """Base user schema"""
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: EmailStr = Field(..., description="Email address")


class UserCreate(UserBase):
    """Schema for creating a new user (admin only)"""
    password: str = Field(..., min_length=12, description="Password (min 12 chars)")
    role: UserRole = Field(default=UserRole.VIEWER, description="User role")


class UserUpdate(BaseModel):
    """Schema for updating user information"""
    email: Optional[EmailStr] = Field(None, description="New email address")
    role: Optional[UserRole] = Field(None, description="New role (admin only)")
    is_active: Optional[bool] = Field(None, description="Account active status (admin only)")


class UserChangePassword(BaseModel):
    """Schema for changing user password"""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=12, description="New password (min 12 chars)")


class PasswordResetRequest(BaseModel):
    """Request password reset via email"""
    email: EmailStr = Field(..., description="Email address associated with the account")


class PasswordResetValidate(BaseModel):
    """Validate password reset token"""
    token: str = Field(..., description="Password reset token from email")


class PasswordResetConfirm(BaseModel):
    """Confirm password reset with new password"""
    token: str = Field(..., description="Password reset token from email")
    new_password: str = Field(..., min_length=12, description="New password (min 12 chars)")


class PasswordResetResponse(BaseModel):
    """Password reset response"""
    message: str = Field(..., description="Status message")
    success: bool = Field(..., description="Whether the operation succeeded")


class AccountUnlockRequest(BaseModel):
    """Request account unlock via email"""
    email: EmailStr = Field(..., description="Email address associated with the locked account")


class AccountUnlockConfirm(BaseModel):
    """Confirm account unlock with token"""
    token: str = Field(..., description="Account unlock token from email")


class AccountUnlockResponse(BaseModel):
    """Account unlock response"""
    message: str = Field(..., description="Status message")
    success: bool = Field(..., description="Whether the operation succeeded")


class UserResponse(UserBase):
    """User response schema (public info)"""
    id: UUID
    role: UserRole
    is_active: bool
    is_locked: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


# ==================== API Key Schemas ====================

class APIKeyCreate(BaseModel):
    """Schema for creating API key"""
    key_name: str = Field(..., min_length=1, max_length=100, description="Descriptive name for key")
    expires_days: Optional[int] = Field(None, ge=1, le=365, description="Days until expiration (optional)")


class APIKeyResponse(BaseModel):
    """API key response (only shown once at creation)"""
    id: UUID
    key_name: str
    api_key: str = Field(..., description="Full API key (ONLY SHOWN ONCE)")
    key_prefix: str = Field(..., description="Key prefix for identification")
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyInfo(BaseModel):
    """API key info (without secret)"""
    id: UUID
    key_name: str
    key_prefix: str
    is_active: bool
    last_used: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== User Management Schemas ====================

class UserListResponse(BaseModel):
    """List of users with pagination"""
    users: list[UserResponse]
    total: int
    page: int
    page_size: int


class UnlockAccountRequest(BaseModel):
    """Request to unlock a locked account"""
    user_id: UUID = Field(..., description="User ID to unlock")


# ==================== Current User Context ====================

class CurrentUserContext(BaseModel):
    """Current authenticated user context"""
    user: UserResponse
    permissions: list[str] = Field(default_factory=list, description="User permissions")

    @staticmethod
    def from_user(user) -> "CurrentUserContext":
        """Create context from User model"""
        permissions = []

        # Define role-based permissions
        if user.role == UserRole.ADMIN:
            permissions = [
                "users:create",
                "users:read",
                "users:update",
                "users:delete",
                "reports:create",
                "reports:read",
                "reports:update",
                "reports:delete",
                "alerts:read",
                "alerts:update",
                "system:manage",
            ]
        elif user.role == UserRole.ANALYST:
            permissions = [
                "reports:create",
                "reports:read",
                "reports:update",
                "alerts:read",
                "alerts:update",
            ]
        elif user.role == UserRole.VIEWER:
            permissions = [
                "reports:read",
                "alerts:read",
            ]

        return CurrentUserContext(
            user=UserResponse.model_validate(user),
            permissions=permissions
        )
