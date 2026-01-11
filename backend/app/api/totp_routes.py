"""
TOTP Two-Factor Authentication API routes.

Endpoints:
- GET /2fa/status - Get 2FA status
- POST /2fa/setup - Start 2FA setup (generate secret)
- POST /2fa/verify - Verify and enable 2FA
- POST /2fa/disable - Disable 2FA
- POST /2fa/backup-codes/regenerate - Regenerate backup codes
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.dependencies.auth import get_current_user
from app.services.totp_service import TOTPService, TOTPError
from app.schemas.totp_schemas import (
    TOTPSetupResponse,
    TOTPVerifyRequest,
    TOTPEnableResponse,
    TOTPDisableRequest,
    TOTPDisableResponse,
    TOTPStatusResponse,
    TOTPRegenerateCodesRequest,
    TOTPBackupCodesResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/2fa", tags=["Two-Factor Authentication"])


@router.get(
    "/status",
    response_model=TOTPStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get 2FA status"
)
async def get_2fa_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the current 2FA status for the authenticated user.

    **Returns:**
    - Whether 2FA is enabled
    - When 2FA was enabled (if enabled)
    - Number of remaining backup codes
    """
    service = TOTPService(db)

    return TOTPStatusResponse(
        enabled=current_user.totp_enabled,
        verified_at=current_user.totp_verified_at,
        backup_codes_remaining=service.get_backup_codes_count(current_user)
    )


@router.post(
    "/setup",
    response_model=TOTPSetupResponse,
    status_code=status.HTTP_200_OK,
    summary="Start 2FA setup"
)
async def setup_2fa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start the 2FA setup process.

    **Process:**
    1. Generates a new TOTP secret
    2. Returns secret and QR code
    3. User scans QR code with authenticator app
    4. User calls /2fa/verify with code to complete setup

    **Note:**
    - Can be called even if 2FA is already enabled (to reset)
    - 2FA is not active until /2fa/verify is called

    **Returns:**
    - TOTP secret (for manual entry)
    - Provisioning URI (for QR code)
    - Base64-encoded QR code image
    """
    service = TOTPService(db)

    secret, provisioning_uri = service.generate_secret(current_user)
    qr_code = service.generate_qr_code(provisioning_uri)

    logger.info(f"2FA setup initiated for user: {current_user.username}")

    return TOTPSetupResponse(
        secret=secret,
        provisioning_uri=provisioning_uri,
        qr_code=qr_code
    )


@router.post(
    "/verify",
    response_model=TOTPEnableResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify and enable 2FA"
)
async def verify_and_enable_2fa(
    verify_request: TOTPVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify TOTP code and enable 2FA.

    **Prerequisites:**
    - Must have called /2fa/setup first
    - Must provide valid 6-digit code from authenticator app

    **What happens:**
    - Validates the TOTP code
    - Enables 2FA for the account
    - Generates backup codes

    **Important:**
    - Store backup codes securely
    - Backup codes are only shown once
    - Each backup code can only be used once
    """
    service = TOTPService(db)

    try:
        backup_codes = service.verify_and_enable(current_user, verify_request.code)
    except TOTPError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return TOTPEnableResponse(
        success=True,
        backup_codes=backup_codes,
        message="Two-factor authentication has been enabled. Store your backup codes securely."
    )


@router.post(
    "/disable",
    response_model=TOTPDisableResponse,
    status_code=status.HTTP_200_OK,
    summary="Disable 2FA"
)
async def disable_2fa(
    disable_request: TOTPDisableRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Disable 2FA for the current user.

    **Requirements:**
    - Must provide current password

    **What happens:**
    - Removes TOTP secret
    - Clears backup codes
    - Disables 2FA requirement for login
    """
    if not current_user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is not enabled"
        )

    service = TOTPService(db)

    try:
        service.disable(current_user, disable_request.password)
    except TOTPError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return TOTPDisableResponse(
        success=True,
        message="Two-factor authentication has been disabled."
    )


@router.post(
    "/backup-codes/regenerate",
    response_model=TOTPBackupCodesResponse,
    status_code=status.HTTP_200_OK,
    summary="Regenerate backup codes"
)
async def regenerate_backup_codes(
    regenerate_request: TOTPRegenerateCodesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Regenerate backup codes.

    **Requirements:**
    - 2FA must be enabled
    - Must provide valid TOTP code

    **What happens:**
    - Invalidates all existing backup codes
    - Generates new backup codes

    **Important:**
    - Store new backup codes securely
    - Previous backup codes will no longer work
    """
    if not current_user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is not enabled"
        )

    service = TOTPService(db)

    try:
        backup_codes = service.regenerate_backup_codes(current_user, regenerate_request.code)
    except TOTPError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return TOTPBackupCodesResponse(
        backup_codes=backup_codes,
        message="Backup codes have been regenerated. Previous codes are no longer valid."
    )
