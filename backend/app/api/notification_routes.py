"""
Notification API Routes

Endpoints for managing user notifications.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.user import User
from app.models.notification import NotificationType, NotificationCategory
from app.services.notification_service import NotificationService
from app.schemas.notification_schemas import (
    NotificationCreate,
    NotificationResponse,
    NotificationListResponse,
    NotificationCountResponse,
    BroadcastNotificationCreate
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    unread_only: bool = Query(False, description="Only return unread notifications"),
    category: Optional[NotificationCategory] = Query(None, description="Filter by category"),
    notification_type: Optional[NotificationType] = Query(None, description="Filter by type"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get notifications for the current user.

    Returns paginated list of notifications with unread count.
    """
    notifications, total, unread_count = NotificationService.get_user_notifications(
        db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        unread_only=unread_only,
        category=category,
        notification_type=notification_type
    )

    return NotificationListResponse(
        notifications=notifications,
        total=total,
        unread_count=unread_count,
        skip=skip,
        limit=limit
    )


@router.get("/count", response_model=NotificationCountResponse)
async def get_notification_counts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get notification counts for the current user.

    Returns total, unread, and counts by type/category.
    """
    counts = NotificationService.get_notification_counts(db, current_user.id)
    return NotificationCountResponse(**counts)


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific notification by ID."""
    notification = NotificationService.get_notification_by_id(
        db, notification_id, current_user.id
    )
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    return notification


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark a notification as read."""
    notification = NotificationService.mark_as_read(
        db, notification_id, current_user.id
    )
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    return notification


@router.post("/read-all", status_code=status.HTTP_200_OK)
async def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark all notifications as read for the current user."""
    count = NotificationService.mark_all_as_read(db, current_user.id)
    return {"message": f"Marked {count} notifications as read"}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a notification."""
    success = NotificationService.delete_notification(
        db, notification_id, current_user.id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    return None


@router.delete("/read/all", status_code=status.HTTP_200_OK)
async def delete_all_read_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete all read notifications for the current user."""
    count = NotificationService.delete_all_read(db, current_user.id)
    return {"message": f"Deleted {count} read notifications"}


# Admin endpoints

@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    data: NotificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """
    Create a notification for a user (admin only).

    If user_id is not provided, creates notification for the requesting user.
    """
    target_user_id = data.user_id or current_user.id

    notification = NotificationService.create_notification(
        db,
        user_id=target_user_id,
        title=data.title,
        message=data.message,
        notification_type=data.notification_type,
        category=data.category,
        link=data.link,
        link_text=data.link_text,
        expires_at=data.expires_at
    )
    return notification


@router.post("/broadcast", status_code=status.HTTP_201_CREATED)
async def broadcast_notification(
    data: BroadcastNotificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """
    Broadcast a notification to all active users (admin only).
    """
    count = NotificationService.broadcast_notification(
        db,
        title=data.title,
        message=data.message,
        notification_type=data.notification_type,
        category=data.category,
        link=data.link,
        link_text=data.link_text,
        expires_at=data.expires_at
    )
    return {"message": f"Notification broadcast to {count} users"}
