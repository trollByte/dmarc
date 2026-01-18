"""
User Notification Models

Stores user notifications for the notification center feature.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class NotificationType(str, PyEnum):
    """Types of notifications"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    ALERT = "alert"


class NotificationCategory(str, PyEnum):
    """Categories of notifications"""
    SYSTEM = "system"
    REPORT = "report"
    ALERT = "alert"
    SECURITY = "security"
    POLICY = "policy"


class UserNotification(Base):
    """User notification model for the notification center"""
    __tablename__ = "user_notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Notification content
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(Enum(NotificationType), default=NotificationType.INFO, nullable=False)
    category = Column(Enum(NotificationCategory), default=NotificationCategory.SYSTEM, nullable=False)

    # Optional link to related resource
    link = Column(String(500), nullable=True)
    link_text = Column(String(100), nullable=True)

    # Read status
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    read_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True)

    # Relationship
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<UserNotification(id={self.id}, user_id={self.user_id}, title={self.title[:30]})>"

    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = datetime.utcnow()

    @property
    def is_expired(self) -> bool:
        """Check if notification has expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
