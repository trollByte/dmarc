"""
Authentication service for user management and JWT tokens.

Handles:
- Password hashing and verification (bcrypt, 12 rounds)
- JWT access and refresh token generation
- API key generation and hashing (SHA256)
- Token validation and refresh
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple
import secrets
import hashlib
import re

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User, UserAPIKey, RefreshToken, UserRole

settings = get_settings()

# Password hashing context (bcrypt with 12 rounds)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


class PasswordValidationError(Exception):
    """Raised when password doesn't meet policy requirements"""
    pass


class AuthService:
    """Service for authentication and authorization operations"""

    # ==================== Password Management ====================

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using bcrypt (12 rounds).

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against hashed version.

        Args:
            plain_password: Plain text password
            hashed_password: Bcrypt hashed password

        Returns:
            True if password matches, False otherwise
        """
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def validate_password_policy(password: str) -> None:
        """
        Validate password against security policy.

        Args:
            password: Password to validate

        Raises:
            PasswordValidationError: If password doesn't meet requirements
        """
        if len(password) < settings.password_min_length:
            raise PasswordValidationError(
                f"Password must be at least {settings.password_min_length} characters long"
            )

        if settings.password_require_uppercase and not re.search(r"[A-Z]", password):
            raise PasswordValidationError("Password must contain at least one uppercase letter")

        if settings.password_require_lowercase and not re.search(r"[a-z]", password):
            raise PasswordValidationError("Password must contain at least one lowercase letter")

        if settings.password_require_digit and not re.search(r"\d", password):
            raise PasswordValidationError("Password must contain at least one digit")

        if settings.password_require_special and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise PasswordValidationError("Password must contain at least one special character")

    # ==================== JWT Token Management ====================

    @staticmethod
    def create_access_token(user_id: str, username: str, role: UserRole) -> str:
        """
        Create JWT access token.

        Args:
            user_id: User UUID as string
            username: Username
            role: User role

        Returns:
            Encoded JWT token
        """
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)

        payload = {
            "sub": user_id,
            "username": username,
            "role": role.value,
            "type": "access",
            "exp": expire,
            "iat": datetime.utcnow(),
        }

        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    @staticmethod
    def create_refresh_token(user_id: str) -> str:
        """
        Create JWT refresh token (for token renewal).

        Args:
            user_id: User UUID as string

        Returns:
            Encoded JWT refresh token
        """
        expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)

        payload = {
            "sub": user_id,
            "type": "refresh",
            "exp": expire,
            "iat": datetime.utcnow(),
        }

        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    @staticmethod
    def decode_token(token: str) -> dict:
        """
        Decode and validate JWT token.

        Args:
            token: JWT token string

        Returns:
            Token payload dict

        Raises:
            JWTError: If token is invalid or expired
        """
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

    @staticmethod
    def create_token_pair(user: User) -> Tuple[str, str]:
        """
        Create access + refresh token pair for user.

        Args:
            user: User model instance

        Returns:
            Tuple of (access_token, refresh_token)
        """
        role = user.role if isinstance(user.role, UserRole) else UserRole(user.role)
        access_token = AuthService.create_access_token(
            str(user.id),
            user.username,
            role
        )
        refresh_token = AuthService.create_refresh_token(str(user.id))
        return access_token, refresh_token

    # ==================== API Key Management ====================

    @staticmethod
    def generate_api_key() -> Tuple[str, str, str]:
        """
        Generate cryptographically secure API key.

        Returns:
            Tuple of (api_key, key_hash, key_prefix)
            - api_key: Full key to display once to user (e.g., "dmarc_abcd1234...")
            - key_hash: SHA256 hash to store in database
            - key_prefix: First 8 chars for user reference (e.g., "dmarc_ab")
        """
        # Generate 32-byte random key
        random_bytes = secrets.token_bytes(32)
        key_suffix = random_bytes.hex()

        # Format: dmarc_<64 hex chars>
        api_key = f"dmarc_{key_suffix}"

        # Hash with SHA256 (store hash, never plaintext)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Prefix for display (first 8 chars)
        key_prefix = api_key[:8]

        return api_key, key_hash, key_prefix

    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """
        Hash API key with SHA256.

        Args:
            api_key: Plain text API key

        Returns:
            SHA256 hash as hex string
        """
        return hashlib.sha256(api_key.encode()).hexdigest()

    @staticmethod
    def validate_api_key(db: Session, api_key: str) -> Optional[User]:
        """
        Validate API key and return associated user.

        Args:
            db: Database session
            api_key: API key from request

        Returns:
            User if key is valid and active, None otherwise
        """
        key_hash = AuthService.hash_api_key(api_key)

        # Find API key
        api_key_obj = db.query(UserAPIKey).filter(
            UserAPIKey.key_hash == key_hash,
            UserAPIKey.is_active == True
        ).first()

        if not api_key_obj:
            return None

        # Check expiration
        if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
            return None

        # Update last used
        api_key_obj.last_used = datetime.utcnow()
        db.commit()

        # Return user if active
        user = db.query(User).filter(User.id == api_key_obj.user_id).first()
        if user and user.is_active and not user.is_locked:
            return user

        return None

    # ==================== User Authentication ====================

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """
        Authenticate user with username and password.

        Args:
            db: Database session
            username: Username or email
            password: Plain text password

        Returns:
            User if authentication successful, None otherwise
        """
        # Find user by username or email
        user = db.query(User).filter(
            (User.username == username) | (User.email == username)
        ).first()

        if not user:
            return None

        # Check if account is locked
        if user.is_locked:
            # Auto-unlock if lockout duration has elapsed.
            # Use updated_at as a proxy for when the lock occurred.
            lockout_minutes = getattr(settings, 'account_lockout_duration_minutes', 30)
            if user.updated_at and (datetime.utcnow() - user.updated_at) >= timedelta(minutes=lockout_minutes):
                user.is_locked = False
                user.failed_login_attempts = 0
                db.commit()
            else:
                return None

        # Verify password
        if not AuthService.verify_password(password, user.hashed_password):
            # Increment failed login attempts
            user.failed_login_attempts += 1

            # Lock account if too many failures
            if user.failed_login_attempts >= settings.max_failed_login_attempts:
                user.is_locked = True

            db.commit()
            return None

        # Success - reset failed attempts and update last login
        user.failed_login_attempts = 0
        user.last_login = datetime.utcnow()
        db.commit()

        return user if user.is_active else None

    @staticmethod
    def store_refresh_token(
        db: Session,
        user_id: str,
        token: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> RefreshToken:
        """
        Store refresh token in database.

        Args:
            db: Database session
            user_id: User UUID
            token: JWT refresh token
            user_agent: Client user agent
            ip_address: Client IP address

        Returns:
            Created RefreshToken object
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)

        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address
        )

        db.add(refresh_token)
        db.commit()
        db.refresh(refresh_token)

        return refresh_token

    @staticmethod
    def validate_refresh_token(db: Session, token: str) -> Optional[User]:
        """
        Validate refresh token and return user.

        Args:
            db: Database session
            token: JWT refresh token

        Returns:
            User if token is valid, None otherwise
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # Find token
        refresh_token = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > datetime.utcnow()
        ).first()

        if not refresh_token:
            return None

        # Get user
        user = db.query(User).filter(User.id == refresh_token.user_id).first()
        if user and user.is_active and not user.is_locked:
            return user

        return None

    @staticmethod
    def revoke_refresh_token(db: Session, token: str) -> bool:
        """
        Revoke refresh token (logout).

        Args:
            db: Database session
            token: JWT refresh token

        Returns:
            True if token was revoked, False if not found
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        refresh_token = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()

        if refresh_token:
            refresh_token.revoked = True
            refresh_token.revoked_at = datetime.utcnow()
            db.commit()
            return True

        return False

    @staticmethod
    def revoke_all_user_tokens(db: Session, user_id: str) -> int:
        """
        Revoke all refresh tokens for a user (logout all sessions).

        Args:
            db: Database session
            user_id: User UUID

        Returns:
            Number of tokens revoked
        """
        tokens = db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False
        ).all()

        count = 0
        for token in tokens:
            token.revoked = True
            token.revoked_at = datetime.utcnow()
            count += 1

        db.commit()
        return count
