"""
Notification Service

Business logic for user notifications.
"""

from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.models.notification import UserNotification, NotificationType, NotificationCategory
from app.models.user import User


class NotificationService:
    """Service for managing user notifications"""

    @staticmethod
    def create_notification(
        db: Session,
        user_id: UUID,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.INFO,
        category: NotificationCategory = NotificationCategory.SYSTEM,
        link: Optional[str] = None,
        link_text: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> UserNotification:
        """Create a new notification for a user"""
        notification = UserNotification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            category=category,
            link=link,
            link_text=link_text,
            expires_at=expires_at
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def broadcast_notification(
        db: Session,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.INFO,
        category: NotificationCategory = NotificationCategory.SYSTEM,
        link: Optional[str] = None,
        link_text: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> int:
        """Broadcast a notification to all active users"""
        users = db.query(User).filter(User.is_active == True).all()
        count = 0

        for user in users:
            notification = UserNotification(
                user_id=user.id,
                title=title,
                message=message,
                notification_type=notification_type,
                category=category,
                link=link,
                link_text=link_text,
                expires_at=expires_at
            )
            db.add(notification)
            count += 1

        db.commit()
        return count

    @staticmethod
    def get_user_notifications(
        db: Session,
        user_id: UUID,
        skip: int = 0,
        limit: int = 50,
        unread_only: bool = False,
        category: Optional[NotificationCategory] = None,
        notification_type: Optional[NotificationType] = None
    ) -> Tuple[List[UserNotification], int, int]:
        """
        Get notifications for a user with pagination

        Returns: (notifications, total_count, unread_count)
        """
        query = db.query(UserNotification).filter(
            UserNotification.user_id == user_id
        )

        # Exclude expired notifications
        query = query.filter(
            (UserNotification.expires_at == None) |
            (UserNotification.expires_at > datetime.utcnow())
        )

        if unread_only:
            query = query.filter(UserNotification.is_read == False)

        if category:
            query = query.filter(UserNotification.category == category)

        if notification_type:
            query = query.filter(UserNotification.notification_type == notification_type)

        # Get total count
        total = query.count()

        # Get unread count (separate query for accuracy)
        unread = db.query(func.count(UserNotification.id)).filter(
            and_(
                UserNotification.user_id == user_id,
                UserNotification.is_read == False,
                (UserNotification.expires_at == None) |
                (UserNotification.expires_at > datetime.utcnow())
            )
        ).scalar()

        # Get paginated results
        notifications = query.order_by(
            UserNotification.created_at.desc()
        ).offset(skip).limit(limit).all()

        return notifications, total, unread

    @staticmethod
    def get_notification_by_id(
        db: Session,
        notification_id: UUID,
        user_id: UUID
    ) -> Optional[UserNotification]:
        """Get a specific notification (must belong to user)"""
        return db.query(UserNotification).filter(
            and_(
                UserNotification.id == notification_id,
                UserNotification.user_id == user_id
            )
        ).first()

    @staticmethod
    def mark_as_read(
        db: Session,
        notification_id: UUID,
        user_id: UUID
    ) -> Optional[UserNotification]:
        """Mark a notification as read"""
        notification = NotificationService.get_notification_by_id(
            db, notification_id, user_id
        )
        if notification:
            notification.mark_as_read()
            db.commit()
            db.refresh(notification)
        return notification

    @staticmethod
    def mark_all_as_read(db: Session, user_id: UUID) -> int:
        """Mark all user notifications as read"""
        result = db.query(UserNotification).filter(
            and_(
                UserNotification.user_id == user_id,
                UserNotification.is_read == False
            )
        ).update({
            UserNotification.is_read: True,
            UserNotification.read_at: datetime.utcnow()
        })
        db.commit()
        return result

    @staticmethod
    def delete_notification(
        db: Session,
        notification_id: UUID,
        user_id: UUID
    ) -> bool:
        """Delete a notification (must belong to user)"""
        notification = NotificationService.get_notification_by_id(
            db, notification_id, user_id
        )
        if notification:
            db.delete(notification)
            db.commit()
            return True
        return False

    @staticmethod
    def delete_all_read(db: Session, user_id: UUID) -> int:
        """Delete all read notifications for a user"""
        result = db.query(UserNotification).filter(
            and_(
                UserNotification.user_id == user_id,
                UserNotification.is_read == True
            )
        ).delete()
        db.commit()
        return result

    @staticmethod
    def get_notification_counts(db: Session, user_id: UUID) -> dict:
        """Get notification counts by type and category"""
        base_query = db.query(UserNotification).filter(
            and_(
                UserNotification.user_id == user_id,
                (UserNotification.expires_at == None) |
                (UserNotification.expires_at > datetime.utcnow())
            )
        )

        total = base_query.count()
        unread = base_query.filter(UserNotification.is_read == False).count()

        # Count by type
        by_type = {}
        for ntype in NotificationType:
            count = base_query.filter(
                UserNotification.notification_type == ntype
            ).count()
            by_type[ntype.value] = count

        # Count by category
        by_category = {}
        for cat in NotificationCategory:
            count = base_query.filter(
                UserNotification.category == cat
            ).count()
            by_category[cat.value] = count

        return {
            "total": total,
            "unread": unread,
            "by_type": by_type,
            "by_category": by_category
        }

    @staticmethod
    def cleanup_expired(db: Session) -> int:
        """Delete expired notifications (for scheduled task)"""
        result = db.query(UserNotification).filter(
            UserNotification.expires_at < datetime.utcnow()
        ).delete()
        db.commit()
        return result

    @staticmethod
    def create_system_notification(
        db: Session,
        user_id: UUID,
        title: str,
        message: str,
        link: Optional[str] = None
    ) -> UserNotification:
        """Helper to create a system notification"""
        return NotificationService.create_notification(
            db, user_id, title, message,
            notification_type=NotificationType.INFO,
            category=NotificationCategory.SYSTEM,
            link=link
        )

    @staticmethod
    def create_alert_notification(
        db: Session,
        user_id: UUID,
        title: str,
        message: str,
        alert_type: NotificationType = NotificationType.WARNING,
        link: Optional[str] = None
    ) -> UserNotification:
        """Helper to create an alert notification"""
        return NotificationService.create_notification(
            db, user_id, title, message,
            notification_type=alert_type,
            category=NotificationCategory.ALERT,
            link=link
        )

    @staticmethod
    def create_report_notification(
        db: Session,
        user_id: UUID,
        title: str,
        message: str,
        report_link: Optional[str] = None
    ) -> UserNotification:
        """Helper to create a report notification"""
        return NotificationService.create_notification(
            db, user_id, title, message,
            notification_type=NotificationType.SUCCESS,
            category=NotificationCategory.REPORT,
            link=report_link,
            link_text="View Report"
        )
