"""
SQLAlchemy models for DMARC Dashboard.

All models are exported from this module for easy importing.
"""

# DMARC models
from app.models.dmarc import IngestedReport, DmarcReport, DmarcRecord

# User authentication models
from app.models.user import User, UserAPIKey, RefreshToken, PasswordResetToken, UserRole

# Alert models
from app.models.alert import (
    AlertHistory, AlertRule, AlertSuppression,
    AlertSeverity, AlertType, AlertStatus
)

# Analytics models
from app.models.analytics import (
    GeoLocationCache, MLModel, MLPrediction, AnalyticsCache
)

# Audit models
from app.models.audit import (
    AuditLog, AuditAction, AuditCategory, get_category_for_action
)

# Retention models
from app.models.retention import (
    RetentionPolicy, RetentionLog, RetentionTarget
)

__all__ = [
    # DMARC models
    "IngestedReport",
    "DmarcReport",
    "DmarcRecord",
    # User models
    "User",
    "UserAPIKey",
    "RefreshToken",
    "PasswordResetToken",
    "UserRole",
    # Alert models
    "AlertHistory",
    "AlertRule",
    "AlertSuppression",
    "AlertSeverity",
    "AlertType",
    "AlertStatus",
    # Analytics models
    "GeoLocationCache",
    "MLModel",
    "MLPrediction",
    "AnalyticsCache",
    # Audit models
    "AuditLog",
    "AuditAction",
    "AuditCategory",
    "get_category_for_action",
    # Retention models
    "RetentionPolicy",
    "RetentionLog",
    "RetentionTarget",
]
