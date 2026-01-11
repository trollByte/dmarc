"""
Pydantic schemas for TOTP Two-Factor Authentication.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class TOTPSetupResponse(BaseModel):
    """Response when starting 2FA setup"""
    secret: str = Field(..., description="Base32 encoded TOTP secret (store securely)")
    provisioning_uri: str = Field(..., description="URI for QR code generation")
    qr_code: str = Field(..., description="Base64-encoded QR code PNG image")


class TOTPVerifyRequest(BaseModel):
    """Request to verify TOTP code"""
    code: str = Field(..., min_length=6, max_length=6, description="6-digit TOTP code")


class TOTPEnableResponse(BaseModel):
    """Response when 2FA is enabled"""
    success: bool = Field(..., description="Whether 2FA was enabled")
    backup_codes: List[str] = Field(..., description="Backup codes (store securely)")
    message: str = Field(..., description="Status message")


class TOTPDisableRequest(BaseModel):
    """Request to disable 2FA"""
    password: str = Field(..., description="Current password for verification")


class TOTPDisableResponse(BaseModel):
    """Response when 2FA is disabled"""
    success: bool = Field(..., description="Whether 2FA was disabled")
    message: str = Field(..., description="Status message")


class TOTPStatusResponse(BaseModel):
    """2FA status for current user"""
    enabled: bool = Field(..., description="Whether 2FA is enabled")
    verified_at: Optional[datetime] = Field(None, description="When 2FA was enabled")
    backup_codes_remaining: int = Field(..., description="Number of backup codes remaining")


class TOTPRegenerateCodesRequest(BaseModel):
    """Request to regenerate backup codes"""
    code: str = Field(..., min_length=6, max_length=6, description="Current 6-digit TOTP code")


class TOTPBackupCodesResponse(BaseModel):
    """Response with backup codes"""
    backup_codes: List[str] = Field(..., description="New backup codes (store securely)")
    message: str = Field(..., description="Status message")


class TOTPLoginRequest(BaseModel):
    """Login request with optional 2FA code"""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")
    totp_code: Optional[str] = Field(None, min_length=6, max_length=6, description="6-digit TOTP code")
    backup_code: Optional[str] = Field(None, description="Backup code (format: XXXX-XXXX)")
