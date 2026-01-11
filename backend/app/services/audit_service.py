"""
Audit Service for logging user actions.

Provides:
- Centralized audit logging
- Async logging to prevent blocking
- Query and filtering of audit logs
- Retention management
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.models import User, AuditLog, AuditAction, AuditCategory, get_category_for_action

logger = logging.getLogger(__name__)


class AuditService:
    """Service for managing audit logs"""

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        action: AuditAction,
        user: Optional[User] = None,
        user_id: Optional[UUID] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        description: Optional[str] = None,
        old_value: Optional[Dict] = None,
        new_value: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
        request_method: Optional[str] = None,
        request_path: Optional[str] = None,
        response_status: Optional[int] = None,
    ) -> AuditLog:
        """
        Create an audit log entry.

        Args:
            action: The action being logged
            user: User performing the action (optional)
            user_id: User ID if user object not available
            username: Username if user object not available
            ip_address: Client IP address
            user_agent: Client user agent
            target_type: Type of target (e.g., "user", "report")
            target_id: ID of the target
            description: Human-readable description
            old_value: Previous state (for updates)
            new_value: New state (for updates)
            metadata: Additional context
            request_method: HTTP method
            request_path: Request path
            response_status: HTTP response status

        Returns:
            Created AuditLog entry
        """
        category = get_category_for_action(action)

        entry = AuditLog(
            action=action.value,
            category=category.value,
            user_id=user.id if user else user_id,
            username=user.username if user else username,
            ip_address=ip_address,
            user_agent=user_agent,
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
            description=description,
            old_value=old_value,
            new_value=new_value,
            metadata=metadata,
            request_method=request_method,
            request_path=request_path,
            response_status=response_status,
        )

        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)

        logger.debug(f"Audit log created: {action.value} by {entry.username}")

        return entry

    def log_login(
        self,
        user: User,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> AuditLog:
        """Log a login attempt"""
        action = AuditAction.LOGIN if success else AuditAction.LOGIN_FAILED
        description = "Successful login" if success else f"Failed login: {failure_reason or 'Invalid credentials'}"

        return self.log(
            action=action,
            user=user if success else None,
            username=user.username,
            ip_address=ip_address,
            user_agent=user_agent,
            description=description,
        )

    def log_logout(
        self,
        user: User,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log a logout"""
        return self.log(
            action=AuditAction.LOGOUT,
            user=user,
            ip_address=ip_address,
            description="User logged out",
        )

    def log_password_change(
        self,
        user: User,
        ip_address: Optional[str] = None,
        via_reset: bool = False,
    ) -> AuditLog:
        """Log a password change"""
        action = AuditAction.PASSWORD_RESET_COMPLETE if via_reset else AuditAction.PASSWORD_CHANGE
        description = "Password reset completed" if via_reset else "Password changed"

        return self.log(
            action=action,
            user=user,
            ip_address=ip_address,
            description=description,
        )

    def log_user_management(
        self,
        action: AuditAction,
        actor: User,
        target_user: User,
        changes: Optional[Dict] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log user management actions"""
        return self.log(
            action=action,
            user=actor,
            ip_address=ip_address,
            target_type="user",
            target_id=str(target_user.id),
            description=f"{action.value.replace('_', ' ').title()}: {target_user.username}",
            new_value=changes,
        )

    def log_data_export(
        self,
        user: User,
        export_type: str,
        filters: Optional[Dict] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log a data export"""
        return self.log(
            action=AuditAction.REPORT_EXPORT,
            user=user,
            ip_address=ip_address,
            description=f"Exported {export_type}",
            metadata={"export_type": export_type, "filters": filters},
        )

    def get_logs(
        self,
        action: Optional[str] = None,
        category: Optional[str] = None,
        user_id: Optional[UUID] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditLog]:
        """
        Query audit logs with filters.

        Args:
            action: Filter by action type
            category: Filter by category
            user_id: Filter by user ID
            username: Filter by username (partial match)
            ip_address: Filter by IP address
            target_type: Filter by target type
            target_id: Filter by target ID
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum results to return
            offset: Offset for pagination

        Returns:
            List of matching AuditLog entries
        """
        query = self.db.query(AuditLog)

        if action:
            query = query.filter(AuditLog.action == action)
        if category:
            query = query.filter(AuditLog.category == category)
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if username:
            query = query.filter(AuditLog.username.ilike(f"%{username}%"))
        if ip_address:
            query = query.filter(AuditLog.ip_address == ip_address)
        if target_type:
            query = query.filter(AuditLog.target_type == target_type)
        if target_id:
            query = query.filter(AuditLog.target_id == target_id)
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        return query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

    def get_logs_count(
        self,
        action: Optional[str] = None,
        category: Optional[str] = None,
        user_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Get count of audit logs matching filters"""
        query = self.db.query(func.count(AuditLog.id))

        if action:
            query = query.filter(AuditLog.action == action)
        if category:
            query = query.filter(AuditLog.category == category)
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        return query.scalar() or 0

    def get_user_activity(
        self,
        user_id: UUID,
        days: int = 30,
        limit: int = 50,
    ) -> List[AuditLog]:
        """Get recent activity for a specific user"""
        since = datetime.utcnow() - timedelta(days=days)

        return self.db.query(AuditLog).filter(
            AuditLog.user_id == user_id,
            AuditLog.created_at >= since
        ).order_by(AuditLog.created_at.desc()).limit(limit).all()

    def get_security_events(
        self,
        days: int = 7,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Get security-related events (failed logins, password changes, etc.)"""
        since = datetime.utcnow() - timedelta(days=days)
        security_actions = [
            AuditAction.LOGIN_FAILED.value,
            AuditAction.PASSWORD_CHANGE.value,
            AuditAction.PASSWORD_RESET_COMPLETE.value,
            AuditAction.TOTP_ENABLE.value,
            AuditAction.TOTP_DISABLE.value,
            AuditAction.USER_LOCK.value,
            AuditAction.USER_UNLOCK.value,
        ]

        return self.db.query(AuditLog).filter(
            AuditLog.created_at >= since,
            AuditLog.action.in_(security_actions)
        ).order_by(AuditLog.created_at.desc()).limit(limit).all()

    def get_stats(
        self,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get audit log statistics"""
        since = datetime.utcnow() - timedelta(days=days)

        # Count by action
        action_counts = self.db.query(
            AuditLog.action,
            func.count(AuditLog.id)
        ).filter(
            AuditLog.created_at >= since
        ).group_by(AuditLog.action).all()

        # Count by category
        category_counts = self.db.query(
            AuditLog.category,
            func.count(AuditLog.id)
        ).filter(
            AuditLog.created_at >= since
        ).group_by(AuditLog.category).all()

        # Failed logins
        failed_logins = self.db.query(func.count(AuditLog.id)).filter(
            AuditLog.created_at >= since,
            AuditLog.action == AuditAction.LOGIN_FAILED.value
        ).scalar() or 0

        return {
            "period_days": days,
            "total_events": sum(count for _, count in action_counts),
            "by_action": {action: count for action, count in action_counts},
            "by_category": {cat: count for cat, count in category_counts},
            "failed_logins": failed_logins,
        }

    def cleanup_old_logs(
        self,
        retention_days: int = 90,
    ) -> int:
        """
        Delete audit logs older than retention period.

        Args:
            retention_days: Number of days to retain logs

        Returns:
            Number of logs deleted
        """
        cutoff = datetime.utcnow() - timedelta(days=retention_days)

        deleted = self.db.query(AuditLog).filter(
            AuditLog.created_at < cutoff
        ).delete()

        self.db.commit()

        logger.info(f"Cleaned up {deleted} audit logs older than {retention_days} days")

        return deleted
