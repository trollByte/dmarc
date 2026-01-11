"""
Password Reset Service for self-service password recovery.

Handles:
- Generating secure reset tokens
- Validating reset tokens
- Resetting passwords
- Sending reset emails (placeholder for email integration)
"""

import secrets
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User, PasswordResetToken
from app.services.auth_service import AuthService

settings = get_settings()
logger = logging.getLogger(__name__)


class PasswordResetError(Exception):
    """Raised when password reset fails"""
    pass


class PasswordResetService:
    """Service for password reset operations"""

    # Token expiration (default: 1 hour)
    TOKEN_EXPIRY_HOURS = 1

    def __init__(self, db: Session):
        self.db = db

    def request_reset(
        self,
        email: str,
        request_ip: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Request a password reset for the given email.

        Args:
            email: User's email address
            request_ip: IP address of the requester

        Returns:
            Tuple of (success, reset_token)
            - If user exists: (True, reset_token)
            - If user doesn't exist: (True, None) - same response to prevent enumeration
        """
        # Find user by email
        user = self.db.query(User).filter(
            User.email == email,
            User.is_active == True
        ).first()

        if not user:
            # Return success to prevent email enumeration
            logger.info(f"Password reset requested for unknown email: {email}")
            return True, None

        if user.is_locked:
            logger.warning(f"Password reset requested for locked account: {email}")
            return True, None

        # Invalidate any existing reset tokens
        self._invalidate_existing_tokens(user.id)

        # Generate new reset token
        token, token_hash = self._generate_token()

        # Create reset token record
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(hours=self.TOKEN_EXPIRY_HOURS),
            request_ip=request_ip
        )

        self.db.add(reset_token)
        self.db.commit()

        logger.info(f"Password reset token generated for user: {user.username}")

        return True, token

    def validate_token(self, token: str) -> Optional[User]:
        """
        Validate a password reset token.

        Args:
            token: The reset token to validate

        Returns:
            User if token is valid, None otherwise
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        reset_token = self.db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        ).first()

        if not reset_token:
            return None

        # Get user
        user = self.db.query(User).filter(
            User.id == reset_token.user_id,
            User.is_active == True
        ).first()

        return user

    def reset_password(
        self,
        token: str,
        new_password: str
    ) -> bool:
        """
        Reset password using a valid reset token.

        Args:
            token: The reset token
            new_password: The new password to set

        Returns:
            True if password was reset successfully

        Raises:
            PasswordResetError: If token is invalid or password policy violation
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # Find and validate token
        reset_token = self.db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        ).first()

        if not reset_token:
            raise PasswordResetError("Invalid or expired reset token")

        # Get user
        user = self.db.query(User).filter(
            User.id == reset_token.user_id,
            User.is_active == True
        ).first()

        if not user:
            raise PasswordResetError("User not found")

        # Validate password policy
        try:
            AuthService.validate_password_policy(new_password)
        except Exception as e:
            raise PasswordResetError(str(e))

        # Update password
        user.hashed_password = AuthService.hash_password(new_password)
        user.failed_login_attempts = 0  # Reset failed attempts
        user.is_locked = False  # Unlock account if it was locked

        # Mark token as used
        reset_token.used = True
        reset_token.used_at = datetime.utcnow()

        # Revoke all existing refresh tokens (force re-login)
        AuthService.revoke_all_user_tokens(self.db, str(user.id))

        self.db.commit()

        logger.info(f"Password reset successful for user: {user.username}")

        return True

    def send_reset_email(
        self,
        email: str,
        reset_token: str,
        reset_url_base: str
    ) -> bool:
        """
        Send password reset email.

        Args:
            email: Recipient email address
            reset_token: The reset token
            reset_url_base: Base URL for the reset page

        Returns:
            True if email was sent (or queued) successfully

        Note:
            This is a placeholder. In production, integrate with
            email service (SMTP, SendGrid, AWS SES, etc.)
        """
        reset_url = f"{reset_url_base}?token={reset_token}"

        # TODO: Integrate with actual email service
        logger.info(f"Password reset email would be sent to: {email}")
        logger.info(f"Reset URL: {reset_url}")

        # For now, just log. In production:
        # - Use SMTP or email API
        # - Use HTML templates
        # - Add rate limiting

        return True

    def _generate_token(self) -> Tuple[str, str]:
        """
        Generate a cryptographically secure reset token.

        Returns:
            Tuple of (token, token_hash)
        """
        # Generate 32-byte random token (256 bits)
        token = secrets.token_urlsafe(32)

        # Hash for storage
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        return token, token_hash

    def _invalidate_existing_tokens(self, user_id) -> int:
        """
        Invalidate all existing reset tokens for a user.

        Args:
            user_id: User UUID

        Returns:
            Number of tokens invalidated
        """
        tokens = self.db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used == False
        ).all()

        count = 0
        for token in tokens:
            token.used = True
            token.used_at = datetime.utcnow()
            count += 1

        if count > 0:
            self.db.commit()
            logger.debug(f"Invalidated {count} existing reset tokens for user {user_id}")

        return count

    def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired password reset tokens.

        Returns:
            Number of tokens deleted
        """
        result = self.db.query(PasswordResetToken).filter(
            PasswordResetToken.expires_at < datetime.utcnow()
        ).delete()

        self.db.commit()
        logger.info(f"Cleaned up {result} expired password reset tokens")

        return result
