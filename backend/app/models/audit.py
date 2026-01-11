"""
Audit logging models for tracking user actions.

Implements comprehensive audit trail for:
- User authentication events (login, logout, password changes)
- Data access (reports, exports)
- Administrative actions (user management, configuration changes)
- API usage tracking
"""

from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.database import Base


class AuditAction(str, enum.Enum):
    """Types of auditable actions"""
    # Authentication
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET_REQUEST = "password_reset_request"
    PASSWORD_RESET_COMPLETE = "password_reset_complete"

    # 2FA
    TOTP_SETUP = "totp_setup"
    TOTP_ENABLE = "totp_enable"
    TOTP_DISABLE = "totp_disable"
    TOTP_BACKUP_USED = "totp_backup_used"

    # User Management
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    USER_LOCK = "user_lock"
    USER_UNLOCK = "user_unlock"
    API_KEY_CREATE = "api_key_create"
    API_KEY_DELETE = "api_key_delete"

    # Data Access
    REPORT_VIEW = "report_view"
    REPORT_EXPORT = "report_export"
    ALERT_VIEW = "alert_view"
    ALERT_ACKNOWLEDGE = "alert_acknowledge"
    ALERT_RESOLVE = "alert_resolve"

    # Configuration
    ALERT_RULE_CREATE = "alert_rule_create"
    ALERT_RULE_UPDATE = "alert_rule_update"
    ALERT_RULE_DELETE = "alert_rule_delete"
    SUPPRESSION_CREATE = "suppression_create"
    SUPPRESSION_UPDATE = "suppression_update"
    SUPPRESSION_DELETE = "suppression_delete"

    # System
    BULK_IMPORT = "bulk_import"
    DATA_PURGE = "data_purge"
    SETTINGS_CHANGE = "settings_change"


class AuditCategory(str, enum.Enum):
    """Categories for grouping audit events"""
    AUTHENTICATION = "authentication"
    USER_MANAGEMENT = "user_management"
    DATA_ACCESS = "data_access"
    CONFIGURATION = "configuration"
    SYSTEM = "system"


class AuditLog(Base):
    """
    Audit log entry for tracking user actions.

    Stores detailed information about user actions for security,
    compliance, and troubleshooting purposes.
    """
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Action identification
    action = Column(String(50), nullable=False, index=True)
    category = Column(String(30), nullable=False, index=True)

    # Actor information
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    username = Column(String(50), nullable=True, index=True)  # Denormalized for history
    ip_address = Column(String(45), nullable=True, index=True)
    user_agent = Column(String(500), nullable=True)

    # Target information
    target_type = Column(String(50), nullable=True, index=True)  # e.g., "user", "report", "alert"
    target_id = Column(String(100), nullable=True)  # UUID or other identifier

    # Action details
    description = Column(Text, nullable=True)
    old_value = Column(JSONB, nullable=True)  # Previous state (for updates)
    new_value = Column(JSONB, nullable=True)  # New state (for updates)
    metadata = Column(JSONB, nullable=True)  # Additional context

    # Request information
    request_method = Column(String(10), nullable=True)
    request_path = Column(String(500), nullable=True)
    response_status = Column(Integer, nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, user={self.username})>"


# Helper function to map actions to categories
ACTION_CATEGORIES = {
    AuditAction.LOGIN: AuditCategory.AUTHENTICATION,
    AuditAction.LOGIN_FAILED: AuditCategory.AUTHENTICATION,
    AuditAction.LOGOUT: AuditCategory.AUTHENTICATION,
    AuditAction.PASSWORD_CHANGE: AuditCategory.AUTHENTICATION,
    AuditAction.PASSWORD_RESET_REQUEST: AuditCategory.AUTHENTICATION,
    AuditAction.PASSWORD_RESET_COMPLETE: AuditCategory.AUTHENTICATION,
    AuditAction.TOTP_SETUP: AuditCategory.AUTHENTICATION,
    AuditAction.TOTP_ENABLE: AuditCategory.AUTHENTICATION,
    AuditAction.TOTP_DISABLE: AuditCategory.AUTHENTICATION,
    AuditAction.TOTP_BACKUP_USED: AuditCategory.AUTHENTICATION,
    AuditAction.USER_CREATE: AuditCategory.USER_MANAGEMENT,
    AuditAction.USER_UPDATE: AuditCategory.USER_MANAGEMENT,
    AuditAction.USER_DELETE: AuditCategory.USER_MANAGEMENT,
    AuditAction.USER_LOCK: AuditCategory.USER_MANAGEMENT,
    AuditAction.USER_UNLOCK: AuditCategory.USER_MANAGEMENT,
    AuditAction.API_KEY_CREATE: AuditCategory.USER_MANAGEMENT,
    AuditAction.API_KEY_DELETE: AuditCategory.USER_MANAGEMENT,
    AuditAction.REPORT_VIEW: AuditCategory.DATA_ACCESS,
    AuditAction.REPORT_EXPORT: AuditCategory.DATA_ACCESS,
    AuditAction.ALERT_VIEW: AuditCategory.DATA_ACCESS,
    AuditAction.ALERT_ACKNOWLEDGE: AuditCategory.DATA_ACCESS,
    AuditAction.ALERT_RESOLVE: AuditCategory.DATA_ACCESS,
    AuditAction.ALERT_RULE_CREATE: AuditCategory.CONFIGURATION,
    AuditAction.ALERT_RULE_UPDATE: AuditCategory.CONFIGURATION,
    AuditAction.ALERT_RULE_DELETE: AuditCategory.CONFIGURATION,
    AuditAction.SUPPRESSION_CREATE: AuditCategory.CONFIGURATION,
    AuditAction.SUPPRESSION_UPDATE: AuditCategory.CONFIGURATION,
    AuditAction.SUPPRESSION_DELETE: AuditCategory.CONFIGURATION,
    AuditAction.BULK_IMPORT: AuditCategory.SYSTEM,
    AuditAction.DATA_PURGE: AuditCategory.SYSTEM,
    AuditAction.SETTINGS_CHANGE: AuditCategory.SYSTEM,
}


def get_category_for_action(action: AuditAction) -> AuditCategory:
    """Get the category for an audit action"""
    return ACTION_CATEGORIES.get(action, AuditCategory.SYSTEM)
