"""
Audit Log API routes.

Endpoints:
- GET /audit/logs - List audit logs (admin only)
- GET /audit/logs/{id} - Get audit log detail
- GET /audit/stats - Get audit statistics
- GET /audit/security - Get security events
- GET /audit/user/{user_id} - Get user activity
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, AuditLog, AuditAction, AuditCategory
from app.dependencies.auth import get_current_user, require_role
from app.services.audit_service import AuditService
from app.schemas.audit_schemas import (
    AuditLogEntry,
    AuditLogListResponse,
    AuditLogStatsResponse,
    AuditLogDetailResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["Audit Logs"])


@router.get(
    "/logs",
    response_model=AuditLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="List audit logs"
)
async def list_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action type"),
    category: Optional[str] = Query(None, description="Filter by category"),
    username: Optional[str] = Query(None, description="Filter by username (partial match)"),
    ip_address: Optional[str] = Query(None, description="Filter by IP address"),
    target_type: Optional[str] = Query(None, description="Filter by target type"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=10, le=200, description="Results per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    List audit logs with filtering and pagination.

    **Admin only.**

    **Filters:**
    - action: Specific action type (e.g., "login", "user_create")
    - category: Category (authentication, user_management, data_access, etc.)
    - username: Partial match on username
    - ip_address: Exact match on IP
    - target_type: Type of target (user, report, alert, etc.)
    - start_date/end_date: Date range filter

    **Available Actions:**
    - Authentication: login, login_failed, logout, password_change
    - User Management: user_create, user_update, user_delete
    - Data Access: report_view, report_export, alert_acknowledge
    - Configuration: alert_rule_create, suppression_create
    """
    service = AuditService(db)
    offset = (page - 1) * page_size

    logs = service.get_logs(
        action=action,
        category=category,
        username=username,
        ip_address=ip_address,
        target_type=target_type,
        start_date=start_date,
        end_date=end_date,
        limit=page_size,
        offset=offset,
    )

    total = service.get_logs_count(
        action=action,
        category=category,
        start_date=start_date,
        end_date=end_date,
    )

    return AuditLogListResponse(
        logs=[AuditLogEntry.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/logs/{log_id}",
    response_model=AuditLogDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get audit log detail"
)
async def get_audit_log_detail(
    log_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    Get detailed information about a specific audit log entry.

    **Admin only.**

    Returns full details including old/new values for change tracking.
    """
    log = db.query(AuditLog).filter(AuditLog.id == log_id).first()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log not found"
        )

    return AuditLogDetailResponse.model_validate(log)


@router.get(
    "/stats",
    response_model=AuditLogStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get audit statistics"
)
async def get_audit_stats(
    days: int = Query(30, ge=1, le=365, description="Days to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    Get audit log statistics.

    **Admin only.**

    Returns:
    - Total events in period
    - Breakdown by action type
    - Breakdown by category
    - Failed login count
    """
    service = AuditService(db)
    stats = service.get_stats(days=days)

    return AuditLogStatsResponse(**stats)


@router.get(
    "/security",
    response_model=list[AuditLogEntry],
    status_code=status.HTTP_200_OK,
    summary="Get security events"
)
async def get_security_events(
    days: int = Query(7, ge=1, le=90, description="Days to look back"),
    limit: int = Query(100, ge=10, le=500, description="Maximum results"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    Get security-related audit events.

    **Admin only.**

    Returns security events:
    - Failed logins
    - Password changes/resets
    - 2FA enable/disable
    - Account lock/unlock
    """
    service = AuditService(db)
    logs = service.get_security_events(days=days, limit=limit)

    return [AuditLogEntry.model_validate(log) for log in logs]


@router.get(
    "/user/{user_id}",
    response_model=list[AuditLogEntry],
    status_code=status.HTTP_200_OK,
    summary="Get user activity"
)
async def get_user_activity(
    user_id: UUID,
    days: int = Query(30, ge=1, le=365, description="Days to look back"),
    limit: int = Query(50, ge=10, le=200, description="Maximum results"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    Get activity history for a specific user.

    **Admin only.**

    Returns all audit events associated with the user.
    """
    service = AuditService(db)
    logs = service.get_user_activity(user_id=user_id, days=days, limit=limit)

    return [AuditLogEntry.model_validate(log) for log in logs]


@router.get(
    "/my-activity",
    response_model=list[AuditLogEntry],
    status_code=status.HTTP_200_OK,
    summary="Get my activity"
)
async def get_my_activity(
    days: int = Query(30, ge=1, le=365, description="Days to look back"),
    limit: int = Query(50, ge=10, le=100, description="Maximum results"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get your own activity history.

    Available to all authenticated users.
    """
    service = AuditService(db)
    logs = service.get_user_activity(user_id=current_user.id, days=days, limit=limit)

    return [AuditLogEntry.model_validate(log) for log in logs]
