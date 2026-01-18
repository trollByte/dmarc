"""
Notification Schemas

Pydantic models for notification API requests and responses.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.notification import NotificationType, NotificationCategory


class NotificationCreate(BaseModel):
    """Schema for creating a notification"""
    title: str = Field(..., min_length=1, max_length=255, description="Notification title")
    message: str = Field(..., min_length=1, description="Notification message")
    notification_type: NotificationType = Field(
        default=NotificationType.INFO,
        description="Type of notification"
    )
    category: NotificationCategory = Field(
        default=NotificationCategory.SYSTEM,
        description="Category of notification"
    )
    link: Optional[str] = Field(None, max_length=500, description="Optional link URL")
    link_text: Optional[str] = Field(None, max_length=100, description="Optional link text")
    user_id: Optional[UUID] = Field(None, description="Target user ID (admin only, for targeted notifications)")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration time")


class NotificationUpdate(BaseModel):
    """Schema for updating notification read status"""
    is_read: bool = Field(..., description="Read status")


class NotificationResponse(BaseModel):
    """Schema for notification response"""
    id: UUID
    title: str
    message: str
    notification_type: NotificationType
    category: NotificationCategory
    link: Optional[str] = None
    link_text: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Schema for paginated notification list"""
    notifications: List[NotificationResponse]
    total: int
    unread_count: int
    skip: int
    limit: int


class NotificationCountResponse(BaseModel):
    """Schema for notification count response"""
    total: int
    unread: int
    by_type: dict
    by_category: dict


class BroadcastNotificationCreate(BaseModel):
    """Schema for broadcasting a notification to all users"""
    title: str = Field(..., min_length=1, max_length=255, description="Notification title")
    message: str = Field(..., min_length=1, description="Notification message")
    notification_type: NotificationType = Field(
        default=NotificationType.INFO,
        description="Type of notification"
    )
    category: NotificationCategory = Field(
        default=NotificationCategory.SYSTEM,
        description="Category of notification"
    )
    link: Optional[str] = Field(None, max_length=500, description="Optional link URL")
    link_text: Optional[str] = Field(None, max_length=100, description="Optional link text")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration time")
