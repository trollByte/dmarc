"""
User authentication and authorization models.

Implements JWT-based authentication with role-based access control (RBAC).
Supports both password-based login and API key authentication.
"""

from sqlalchemy import Column, String, DateTime, Boolean, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.database import Base


class UserRole(str, enum.Enum):
    """User roles for RBAC"""
    ADMIN = "admin"          # Full access: user management, system config
    ANALYST = "analyst"      # Read/write: reports, alerts
    VIEWER = "viewer"        # Read-only access


class User(Base):
    """User account with JWT authentication and RBAC"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)

    # Role-based access control - stored as string, validated by Python enum
    role = Column(String(20), nullable=False, default=UserRole.VIEWER.value)

    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    is_locked = Column(Boolean, default=False, nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)

    # Two-Factor Authentication (TOTP)
    totp_secret = Column(String(32), nullable=True)  # Encrypted TOTP secret
    totp_enabled = Column(Boolean, default=False, nullable=False)
    totp_backup_codes = Column(JSONB, nullable=True)  # Hashed backup codes
    totp_verified_at = Column(DateTime, nullable=True)  # When 2FA was verified

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    api_keys = relationship("UserAPIKey", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"


class UserAPIKey(Base):
    """API keys for programmatic access (alternative to JWT)"""
    __tablename__ = "user_api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Key identification (visible to user)
    key_name = Column(String(100), nullable=False)
    key_prefix = Column(String(10), nullable=False, index=True)  # First 8 chars for display

    # Hashed key (SHA256) - never store plaintext
    key_hash = Column(String(64), unique=True, nullable=False, index=True)

    # Key metadata
    is_active = Column(Boolean, default=True, nullable=False)
    last_used = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="api_keys")

    def __repr__(self):
        return f"<UserAPIKey(id={self.id}, key_name={self.key_name}, prefix={self.key_prefix})>"


class PasswordResetToken(Base):
    """Password reset tokens for self-service password recovery"""
    __tablename__ = "password_reset_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Token hash (SHA256) - never store plaintext
    token_hash = Column(String(64), unique=True, nullable=False, index=True)

    # Token metadata
    expires_at = Column(DateTime, nullable=False, index=True)
    used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime, nullable=True)

    # Client information (for audit trail)
    request_ip = Column(String(45), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="password_reset_tokens")

    def __repr__(self):
        return f"<PasswordResetToken(id={self.id}, user_id={self.user_id}, used={self.used})>"


class RefreshToken(Base):
    """JWT refresh tokens for token renewal"""
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Token hash (SHA256) - never store plaintext
    token_hash = Column(String(64), unique=True, nullable=False, index=True)

    # Token metadata
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    # Client information (for audit trail)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")

    def __repr__(self):
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, revoked={self.revoked})>"


class AccountUnlockToken(Base):
    """Account unlock tokens for self-service account recovery"""
    __tablename__ = "account_unlock_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Token hash (SHA256) - never store plaintext
    token_hash = Column(String(64), unique=True, nullable=False, index=True)

    # Token metadata
    expires_at = Column(DateTime, nullable=False, index=True)
    used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime, nullable=True)

    # Client information (for audit trail)
    request_ip = Column(String(45), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="account_unlock_tokens")

    def __repr__(self):
        return f"<AccountUnlockToken(id={self.id}, user_id={self.user_id}, used={self.used})>"
