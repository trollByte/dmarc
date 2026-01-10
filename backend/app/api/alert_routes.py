"""
Alert management API routes.

Endpoints for:
- Alert history and lifecycle (acknowledge, resolve)
- Alert rules (configurable thresholds)
- Alert suppressions (maintenance windows)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import UUID

from app.database import get_db
from app.models import (
    AlertHistory, AlertRule, AlertSuppression,
    AlertSeverity, AlertType, AlertStatus, User
)
from app.services.alerting_v2 import EnhancedAlertService
from app.dependencies.auth import get_current_user, require_admin, require_analyst_or_admin
from app.schemas.alert_schemas import (
    AlertHistoryResponse,
    AcknowledgeAlertRequest,
    ResolveAlertRequest,
    AlertStatsResponse,
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertRuleResponse,
    AlertSuppressionCreate,
    AlertSuppressionUpdate,
    AlertSuppressionResponse,
    BulkAcknowledgeRequest,
    BulkResolveRequest,
    BulkOperationResponse,
)

router = APIRouter(prefix="/alerts", tags=["Alert Management"])


# ==================== Alert History & Lifecycle ====================

@router.get(
    "/active",
    response_model=List[AlertHistoryResponse],
    summary="Get active alerts"
)
async def get_active_alerts(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    limit: int = Query(100, ge=1, le=500, description="Max alerts to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get active alerts (created or acknowledged status).

    **Permissions:** All authenticated users

    **Usage:**
    ```
    GET /alerts/active?domain=example.com&severity=critical&limit=50
    Authorization: Bearer <token>
    ```
    """
    service = EnhancedAlertService(db)
    alerts = service.get_active_alerts(domain=domain, severity=severity, limit=limit)
    return alerts


@router.get(
    "/history",
    response_model=List[AlertHistoryResponse],
    summary="Get alert history"
)
async def get_alert_history(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    alert_type: Optional[AlertType] = Query(None, description="Filter by type"),
    start_date: Optional[datetime] = Query(None, description="Start date (UTC)"),
    end_date: Optional[datetime] = Query(None, description="End date (UTC)"),
    limit: int = Query(100, ge=1, le=500, description="Max alerts to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get historical alerts with filters.

    **Permissions:** All authenticated users

    **Usage:**
    ```
    GET /alerts/history?domain=example.com&alert_type=failure_rate&start_date=2026-01-01T00:00:00Z
    Authorization: Bearer <token>
    ```
    """
    service = EnhancedAlertService(db)
    alerts = service.get_alert_history(
        domain=domain,
        alert_type=alert_type,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
    return alerts


@router.get(
    "/stats",
    response_model=AlertStatsResponse,
    summary="Get alert statistics"
)
async def get_alert_stats(
    days: int = Query(7, ge=1, le=365, description="Days to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get alert statistics for the past N days.

    **Permissions:** All authenticated users

    **Usage:**
    ```
    GET /alerts/stats?days=30
    Authorization: Bearer <token>
    ```

    **Response includes:**
    - Total alerts
    - Breakdown by severity, type, status, domain
    - Average resolution time
    """
    service = EnhancedAlertService(db)
    stats = service.get_alert_stats(days=days)
    return stats


@router.post(
    "/{alert_id}/acknowledge",
    response_model=AlertHistoryResponse,
    summary="Acknowledge alert"
)
async def acknowledge_alert(
    alert_id: UUID,
    request: AcknowledgeAlertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analyst_or_admin())
):
    """
    Acknowledge an alert.

    **Permissions:** Analyst or Admin

    **Usage:**
    ```
    POST /alerts/{alert_id}/acknowledge
    Authorization: Bearer <token>
    {
        "note": "Investigating the issue"
    }
    ```
    """
    service = EnhancedAlertService(db)

    try:
        alert = service.acknowledge_alert(
            str(alert_id),
            str(current_user.id),
            note=request.note
        )
        return alert
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{alert_id}/resolve",
    response_model=AlertHistoryResponse,
    summary="Resolve alert"
)
async def resolve_alert(
    alert_id: UUID,
    request: ResolveAlertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analyst_or_admin())
):
    """
    Resolve an alert.

    **Permissions:** Analyst or Admin

    **Usage:**
    ```
    POST /alerts/{alert_id}/resolve
    Authorization: Bearer <token>
    {
        "note": "Issue fixed - DKIM record updated"
    }
    ```
    """
    service = EnhancedAlertService(db)

    try:
        alert = service.resolve_alert(
            str(alert_id),
            str(current_user.id),
            note=request.note
        )
        return alert
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


def _execute_bulk_operation(
    service: EnhancedAlertService,
    alert_ids: List[UUID],
    user_id: str,
    operation,
    note: Optional[str] = None
) -> BulkOperationResponse:
    """Execute a bulk operation on multiple alerts"""
    success_count = 0
    failed_count = 0
    errors = []

    for alert_id in alert_ids:
        try:
            operation(str(alert_id), user_id, note=note)
            success_count += 1
        except Exception as e:
            failed_count += 1
            errors.append(f"Alert {alert_id}: {str(e)}")

    return BulkOperationResponse(
        success_count=success_count,
        failed_count=failed_count,
        errors=errors
    )


@router.post(
    "/bulk/acknowledge",
    response_model=BulkOperationResponse,
    summary="Bulk acknowledge alerts"
)
async def bulk_acknowledge_alerts(
    request: BulkAcknowledgeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analyst_or_admin())
):
    """
    Acknowledge multiple alerts at once.

    **Permissions:** Analyst or Admin

    **Usage:**
    ```
    POST /alerts/bulk/acknowledge
    Authorization: Bearer <token>
    {
        "alert_ids": ["uuid1", "uuid2", ...],
        "note": "Batch acknowledgement"
    }
    ```
    """
    service = EnhancedAlertService(db)
    return _execute_bulk_operation(
        service,
        request.alert_ids,
        str(current_user.id),
        service.acknowledge_alert,
        request.note
    )


@router.post(
    "/bulk/resolve",
    response_model=BulkOperationResponse,
    summary="Bulk resolve alerts"
)
async def bulk_resolve_alerts(
    request: BulkResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analyst_or_admin())
):
    """
    Resolve multiple alerts at once.

    **Permissions:** Analyst or Admin

    **Usage:**
    ```
    POST /alerts/bulk/resolve
    Authorization: Bearer <token>
    {
        "alert_ids": ["uuid1", "uuid2", ...],
        "note": "Batch resolution"
    }
    ```
    """
    service = EnhancedAlertService(db)
    return _execute_bulk_operation(
        service,
        request.alert_ids,
        str(current_user.id),
        service.resolve_alert,
        request.note
    )


# ==================== Alert Rules ====================

@router.get(
    "/rules",
    response_model=List[AlertRuleResponse],
    summary="List alert rules"
)
async def list_alert_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all alert rules.

    **Permissions:** All authenticated users

    **Usage:**
    ```
    GET /alerts/rules
    Authorization: Bearer <token>
    ```
    """
    rules = db.query(AlertRule).order_by(AlertRule.created_at.desc()).all()
    return rules


@router.post(
    "/rules",
    response_model=AlertRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create alert rule (admin only)"
)
async def create_alert_rule(
    rule_data: AlertRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """
    Create a new alert rule.

    **Permissions:** Admin only

    **Usage:**
    ```
    POST /alerts/rules
    Authorization: Bearer <admin_token>
    {
        "name": "High Failure Rate Warning",
        "description": "Warn when failure rate exceeds 10%",
        "alert_type": "failure_rate",
        "is_enabled": true,
        "severity": "warning",
        "conditions": {
            "failure_rate": {
                "warning": 10.0,
                "critical": 25.0
            }
        },
        "domain_pattern": null,
        "cooldown_minutes": 60,
        "notify_teams": true,
        "notify_email": true
    }
    ```
    """
    # Check if rule name already exists
    existing = db.query(AlertRule).filter(AlertRule.name == rule_data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Alert rule '{rule_data.name}' already exists"
        )

    rule = AlertRule(
        name=rule_data.name,
        description=rule_data.description,
        alert_type=rule_data.alert_type,
        is_enabled=rule_data.is_enabled,
        severity=rule_data.severity,
        conditions=rule_data.conditions,
        domain_pattern=rule_data.domain_pattern,
        cooldown_minutes=rule_data.cooldown_minutes,
        notify_email=rule_data.notify_email,
        notify_teams=rule_data.notify_teams,
        notify_slack=rule_data.notify_slack,
        notify_webhook=rule_data.notify_webhook,
        created_by=current_user.id
    )

    db.add(rule)
    db.commit()
    db.refresh(rule)

    return rule


@router.patch(
    "/rules/{rule_id}",
    response_model=AlertRuleResponse,
    summary="Update alert rule (admin only)"
)
async def update_alert_rule(
    rule_id: UUID,
    rule_data: AlertRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """
    Update an existing alert rule.

    **Permissions:** Admin only
    """
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert rule not found")

    # Update fields
    update_data = rule_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)

    rule.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(rule)

    return rule


@router.delete(
    "/rules/{rule_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete alert rule (admin only)"
)
async def delete_alert_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """
    Delete an alert rule.

    **Permissions:** Admin only
    """
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert rule not found")

    db.delete(rule)
    db.commit()

    return {"message": f"Alert rule '{rule.name}' deleted successfully"}


# ==================== Alert Suppressions ====================

@router.get(
    "/suppressions",
    response_model=List[AlertSuppressionResponse],
    summary="List alert suppressions"
)
async def list_alert_suppressions(
    active_only: bool = Query(False, description="Show only active suppressions"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all alert suppressions.

    **Permissions:** All authenticated users
    """
    query = db.query(AlertSuppression)

    if active_only:
        query = query.filter(AlertSuppression.is_active == True)

    suppressions = query.order_by(AlertSuppression.created_at.desc()).all()
    return suppressions


@router.post(
    "/suppressions",
    response_model=AlertSuppressionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create alert suppression (admin or analyst)"
)
async def create_alert_suppression(
    suppression_data: AlertSuppressionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analyst_or_admin())
):
    """
    Create a new alert suppression.

    **Permissions:** Analyst or Admin

    **Usage:**
    ```
    POST /alerts/suppressions
    Authorization: Bearer <token>
    {
        "name": "Weekend Maintenance Window",
        "description": "Suppress alerts during weekend maintenance",
        "is_active": true,
        "alert_type": null,
        "severity": null,
        "domain": null,
        "starts_at": "2026-01-11T02:00:00Z",
        "ends_at": "2026-01-11T06:00:00Z",
        "recurrence": {
            "type": "weekly",
            "days": ["saturday", "sunday"],
            "hours": [2, 3, 4, 5]
        }
    }
    ```
    """
    suppression = AlertSuppression(
        name=suppression_data.name,
        description=suppression_data.description,
        is_active=suppression_data.is_active,
        alert_type=suppression_data.alert_type,
        severity=suppression_data.severity,
        domain=suppression_data.domain,
        starts_at=suppression_data.starts_at,
        ends_at=suppression_data.ends_at,
        recurrence=suppression_data.recurrence,
        created_by=current_user.id
    )

    db.add(suppression)
    db.commit()
    db.refresh(suppression)

    return suppression


@router.patch(
    "/suppressions/{suppression_id}",
    response_model=AlertSuppressionResponse,
    summary="Update alert suppression (admin or analyst)"
)
async def update_alert_suppression(
    suppression_id: UUID,
    suppression_data: AlertSuppressionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analyst_or_admin())
):
    """
    Update an existing alert suppression.

    **Permissions:** Analyst or Admin
    """
    suppression = db.query(AlertSuppression).filter(AlertSuppression.id == suppression_id).first()
    if not suppression:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert suppression not found")

    # Update fields
    update_data = suppression_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(suppression, key, value)

    suppression.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(suppression)

    return suppression


@router.delete(
    "/suppressions/{suppression_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete alert suppression (admin or analyst)"
)
async def delete_alert_suppression(
    suppression_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analyst_or_admin())
):
    """
    Delete an alert suppression.

    **Permissions:** Analyst or Admin
    """
    suppression = db.query(AlertSuppression).filter(AlertSuppression.id == suppression_id).first()
    if not suppression:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert suppression not found")

    db.delete(suppression)
    db.commit()

    return {"message": f"Alert suppression '{suppression.name}' deleted successfully"}
