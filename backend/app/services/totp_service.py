"""
TOTP Service for Two-Factor Authentication.

Implements:
- TOTP secret generation (RFC 6238)
- QR code generation for authenticator apps
- Code verification
- Backup code generation and validation
"""

import secrets
import hashlib
import base64
import io
import logging
from datetime import datetime
from typing import List, Tuple, Optional

import pyotp
import qrcode
from qrcode.image.pure import PyPNGImage
from sqlalchemy.orm import Session

from app.models import User
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Number of backup codes to generate
BACKUP_CODES_COUNT = 10


class TOTPError(Exception):
    """Raised when TOTP operation fails"""
    pass


class TOTPService:
    """Service for TOTP two-factor authentication"""

    def __init__(self, db: Session):
        self.db = db

    def generate_secret(self, user: User) -> Tuple[str, str]:
        """
        Generate a new TOTP secret for the user.

        Args:
            user: User to generate secret for

        Returns:
            Tuple of (secret, provisioning_uri)

        Note:
            Secret is not saved until verify_and_enable() is called
        """
        # Generate 20-byte (160-bit) random secret
        secret = pyotp.random_base32(length=32)

        # Create provisioning URI for QR code
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name=settings.app_name
        )

        # Store secret temporarily (not enabled yet)
        user.totp_secret = secret
        self.db.commit()

        logger.info(f"TOTP secret generated for user: {user.username}")

        return secret, provisioning_uri

    def generate_qr_code(self, provisioning_uri: str) -> str:
        """
        Generate QR code image as base64 string.

        Args:
            provisioning_uri: TOTP provisioning URI

        Returns:
            Base64-encoded PNG image
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    def verify_code(self, user: User, code: str) -> bool:
        """
        Verify a TOTP code.

        Args:
            user: User to verify for
            code: 6-digit TOTP code

        Returns:
            True if code is valid, False otherwise
        """
        if not user.totp_secret:
            return False

        totp = pyotp.TOTP(user.totp_secret)

        # Allow 1 window of tolerance (30 seconds before/after)
        return totp.verify(code, valid_window=1)

    def verify_and_enable(self, user: User, code: str) -> List[str]:
        """
        Verify initial TOTP code and enable 2FA.

        Args:
            user: User to enable 2FA for
            code: 6-digit TOTP code

        Returns:
            List of backup codes

        Raises:
            TOTPError: If code is invalid or secret not set
        """
        if not user.totp_secret:
            raise TOTPError("TOTP secret not set. Call generate_secret() first.")

        if not self.verify_code(user, code):
            raise TOTPError("Invalid verification code")

        # Generate backup codes
        backup_codes = self._generate_backup_codes()
        hashed_codes = [self._hash_backup_code(c) for c in backup_codes]

        # Enable 2FA
        user.totp_enabled = True
        user.totp_backup_codes = hashed_codes
        user.totp_verified_at = datetime.utcnow()
        self.db.commit()

        logger.info(f"2FA enabled for user: {user.username}")

        return backup_codes

    def disable(self, user: User, password: str) -> bool:
        """
        Disable 2FA for a user.

        Args:
            user: User to disable 2FA for
            password: User's password for verification

        Returns:
            True if disabled successfully

        Raises:
            TOTPError: If password is incorrect
        """
        from app.services.auth_service import AuthService

        if not AuthService.verify_password(password, user.hashed_password):
            raise TOTPError("Invalid password")

        user.totp_secret = None
        user.totp_enabled = False
        user.totp_backup_codes = None
        user.totp_verified_at = None
        self.db.commit()

        logger.info(f"2FA disabled for user: {user.username}")

        return True

    def verify_backup_code(self, user: User, code: str) -> bool:
        """
        Verify and consume a backup code.

        Args:
            user: User to verify for
            code: Backup code (with or without dashes)

        Returns:
            True if code is valid and consumed
        """
        if not user.totp_backup_codes:
            return False

        # Normalize code (remove dashes, uppercase)
        code = code.replace('-', '').upper()
        code_hash = self._hash_backup_code(code)

        # Check if code exists
        if code_hash not in user.totp_backup_codes:
            return False

        # Remove used code
        updated_codes = [c for c in user.totp_backup_codes if c != code_hash]
        user.totp_backup_codes = updated_codes
        self.db.commit()

        logger.info(f"Backup code used for user: {user.username}")

        return True

    def regenerate_backup_codes(self, user: User, code: str) -> List[str]:
        """
        Regenerate backup codes (requires valid TOTP code).

        Args:
            user: User to regenerate codes for
            code: Valid TOTP code

        Returns:
            List of new backup codes

        Raises:
            TOTPError: If code is invalid
        """
        if not user.totp_enabled:
            raise TOTPError("2FA is not enabled")

        if not self.verify_code(user, code):
            raise TOTPError("Invalid verification code")

        backup_codes = self._generate_backup_codes()
        hashed_codes = [self._hash_backup_code(c) for c in backup_codes]

        user.totp_backup_codes = hashed_codes
        self.db.commit()

        logger.info(f"Backup codes regenerated for user: {user.username}")

        return backup_codes

    def get_backup_codes_count(self, user: User) -> int:
        """
        Get count of remaining backup codes.

        Args:
            user: User to check

        Returns:
            Number of remaining backup codes
        """
        if not user.totp_backup_codes:
            return 0
        return len(user.totp_backup_codes)

    def _generate_backup_codes(self) -> List[str]:
        """
        Generate random backup codes.

        Returns:
            List of formatted backup codes (XXXX-XXXX format)
        """
        codes = []
        for _ in range(BACKUP_CODES_COUNT):
            # Generate 8 random alphanumeric characters
            code = secrets.token_hex(4).upper()
            formatted = f"{code[:4]}-{code[4:]}"
            codes.append(formatted)
        return codes

    def _hash_backup_code(self, code: str) -> str:
        """
        Hash a backup code for storage.

        Args:
            code: Backup code (with or without dashes)

        Returns:
            SHA256 hash of the code
        """
        normalized = code.replace('-', '').upper()
        return hashlib.sha256(normalized.encode()).hexdigest()


def require_2fa_verification(user: User, totp_code: Optional[str], backup_code: Optional[str], db: Session) -> bool:
    """
    Utility function to verify 2FA if enabled.

    Args:
        user: User to verify
        totp_code: TOTP code (optional)
        backup_code: Backup code (optional)
        db: Database session

    Returns:
        True if 2FA not enabled or verification successful

    Raises:
        TOTPError: If 2FA enabled but no valid code provided
    """
    if not user.totp_enabled:
        return True

    service = TOTPService(db)

    # Try TOTP code first
    if totp_code and service.verify_code(user, totp_code):
        return True

    # Try backup code
    if backup_code and service.verify_backup_code(user, backup_code):
        return True

    raise TOTPError("Two-factor authentication required")
