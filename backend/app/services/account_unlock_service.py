"""
Account Unlock Service for self-service account recovery.

Handles:
- Generating secure unlock tokens
- Validating unlock tokens
- Unlocking locked accounts
- Sending unlock emails via SMTP (falls back to logging when SMTP is not configured)
"""

import secrets
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User, AccountUnlockToken
from app.services.notifications import NotificationService, SMTPConfig

settings = get_settings()
logger = logging.getLogger(__name__)


class AccountUnlockError(Exception):
    """Raised when account unlock fails"""
    pass


class AccountUnlockService:
    """Service for account unlock operations"""

    # Token expiration (default: 1 hour)
    TOKEN_EXPIRY_HOURS = 1

    def __init__(self, db: Session):
        self.db = db

    def request_unlock(
        self,
        email: str,
        request_ip: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Request an account unlock for the given email.

        Args:
            email: User's email address
            request_ip: IP address of the requester

        Returns:
            Tuple of (success, unlock_token)
            - If user exists and is locked: (True, unlock_token)
            - If user doesn't exist or is not locked: (True, None) - same response to prevent enumeration
        """
        # Find user by email
        user = self.db.query(User).filter(
            User.email == email,
            User.is_active == True
        ).first()

        if not user:
            # Return success to prevent email enumeration
            logger.info(f"Account unlock requested for unknown email: {email}")
            return True, None

        if not user.is_locked:
            # Account not locked - return success to prevent enumeration
            logger.info(f"Account unlock requested for non-locked account: {email}")
            return True, None

        # Invalidate any existing unlock tokens
        self._invalidate_existing_tokens(user.id)

        # Generate new unlock token
        token, token_hash = self._generate_token()

        # Create unlock token record
        unlock_token = AccountUnlockToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(hours=self.TOKEN_EXPIRY_HOURS),
            request_ip=request_ip
        )

        self.db.add(unlock_token)
        self.db.commit()

        logger.info(f"Account unlock token generated for user: {user.username}")

        return True, token

    def validate_token(self, token: str) -> Optional[User]:
        """
        Validate an account unlock token.

        Args:
            token: The unlock token to validate

        Returns:
            User if token is valid, None otherwise
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        unlock_token = self.db.query(AccountUnlockToken).filter(
            AccountUnlockToken.token_hash == token_hash,
            AccountUnlockToken.used == False,
            AccountUnlockToken.expires_at > datetime.utcnow()
        ).first()

        if not unlock_token:
            return None

        # Get user
        user = self.db.query(User).filter(
            User.id == unlock_token.user_id,
            User.is_active == True
        ).first()

        return user

    def unlock_account(
        self,
        token: str
    ) -> bool:
        """
        Unlock account using a valid unlock token.

        Args:
            token: The unlock token

        Returns:
            True if account was unlocked successfully

        Raises:
            AccountUnlockError: If token is invalid
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # Find and validate token
        unlock_token = self.db.query(AccountUnlockToken).filter(
            AccountUnlockToken.token_hash == token_hash,
            AccountUnlockToken.used == False,
            AccountUnlockToken.expires_at > datetime.utcnow()
        ).first()

        if not unlock_token:
            raise AccountUnlockError("Invalid or expired unlock token")

        # Get user
        user = self.db.query(User).filter(
            User.id == unlock_token.user_id,
            User.is_active == True
        ).first()

        if not user:
            raise AccountUnlockError("User not found")

        # Unlock account
        user.is_locked = False
        user.failed_login_attempts = 0

        # Mark token as used
        unlock_token.used = True
        unlock_token.used_at = datetime.utcnow()

        self.db.commit()

        logger.info(f"Account unlocked successfully for user: {user.username}")

        return True

    def send_unlock_email(
        self,
        email: str,
        unlock_token: str,
        unlock_url_base: str
    ) -> bool:
        """
        Send account unlock email via SMTP using the NotificationService.

        Falls back to logging the unlock URL when SMTP is not configured,
        which is useful during development.

        Args:
            email: Recipient email address
            unlock_token: The unlock token
            unlock_url_base: Base URL for the unlock page

        Returns:
            True if email was sent (or logged as fallback) successfully
        """
        unlock_url = f"{unlock_url_base}?token={unlock_token}"

        smtp_host = settings.smtp_host
        smtp_from = settings.smtp_from

        if not smtp_host or not smtp_from:
            logger.info(f"SMTP not configured, logging unlock link for {email}")
            logger.info(f"Unlock URL: {unlock_url}")
            return True

        try:
            notification_service = NotificationService()
            smtp_config = SMTPConfig(
                host=smtp_host,
                port=settings.smtp_port,
                user=settings.smtp_user or None,
                password=settings.smtp_password or None,
                from_address=smtp_from,
                to_address=email,
                use_tls=settings.smtp_use_tls,
            )

            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Account Unlock Request</h2>
                <p>Your DMARC Dashboard account has been locked due to too many failed login attempts.</p>
                <p>Click the link below to unlock your account:</p>
                <p><a href="{unlock_url}" style="background: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">Unlock Account</a></p>
                <p>Or copy this URL: {unlock_url}</p>
                <p>This link expires in {self.TOKEN_EXPIRY_HOURS} hour(s).</p>
                <p>If you did not request this unlock, please contact your administrator.</p>
                <hr>
                <p style="color: #999; font-size: 12px;">DMARC Dashboard</p>
            </body>
            </html>
            """

            notification_service._send_email(
                subject="Account Unlock Request - DMARC Dashboard",
                html_body=html_body,
                config=smtp_config,
            )

            logger.info(f"Account unlock email sent to {email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send account unlock email to {email}: {e}")
            logger.info(f"Unlock URL (fallback): {unlock_url}")
            return True

    def _generate_token(self) -> Tuple[str, str]:
        """
        Generate a cryptographically secure unlock token.

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
        Invalidate all existing unlock tokens for a user.

        Args:
            user_id: User UUID

        Returns:
            Number of tokens invalidated
        """
        tokens = self.db.query(AccountUnlockToken).filter(
            AccountUnlockToken.user_id == user_id,
            AccountUnlockToken.used == False
        ).all()

        count = 0
        for token in tokens:
            token.used = True
            token.used_at = datetime.utcnow()
            count += 1

        if count > 0:
            self.db.commit()
            logger.debug(f"Invalidated {count} existing unlock tokens for user {user_id}")

        return count

    def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired account unlock tokens.

        Returns:
            Number of tokens deleted
        """
        result = self.db.query(AccountUnlockToken).filter(
            AccountUnlockToken.expires_at < datetime.utcnow()
        ).delete()

        self.db.commit()
        logger.info(f"Cleaned up {result} expired account unlock tokens")

        return result
