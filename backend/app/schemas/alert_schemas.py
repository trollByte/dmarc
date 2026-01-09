"""
Pydantic schemas for alert management.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID

from app.models import AlertSeverity, AlertType, AlertStatus


# ==================== Alert History Schemas ====================

class AlertHistoryResponse(BaseModel):
    """Alert history response"""
    id: UUID
    alert_type: AlertType
    severity: AlertSeverity
    fingerprint: str
    title: str
    message: str
    domain: Optional[str]
    current_value: Optional[float]
    threshold_value: Optional[float]
    metadata: Optional[Dict[str, Any]]
    status: AlertStatus
    created_at: datetime
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[UUID]
    resolved_at: Optional[datetime]
    resolved_by: Optional[UUID]
    acknowledgement_note: Optional[str]
    resolution_note: Optional[str]
    notification_sent: bool
    notification_sent_at: Optional[datetime]
    notification_channels: Optional[List[str]]
    cooldown_until: Optional[datetime]

    class Config:
        from_attributes = True


class AcknowledgeAlertRequest(BaseModel):
    """Request to acknowledge an alert"""
    note: Optional[str] = Field(None, max_length=1000, description="Optional acknowledgement note")


class ResolveAlertRequest(BaseModel):
    """Request to resolve an alert"""
    note: Optional[str] = Field(None, max_length=1000, description="Optional resolution note")


class AlertStatsResponse(BaseModel):
    """Alert statistics response"""
    period_days: int
    total_alerts: int
    by_severity: Dict[str, int]
    by_type: Dict[str, int]
    by_status: Dict[str, int]
    by_domain: Dict[str, int]
    avg_resolution_time_hours: Optional[float]


# ==================== Alert Rule Schemas ====================

class AlertRuleCreate(BaseModel):
    """Schema for creating alert rule"""
    name: str = Field(..., min_length=1, max_length=255, description="Rule name")
    description: Optional[str] = Field(None, description="Rule description")
    alert_type: AlertType = Field(..., description="Type of alert")
    is_enabled: bool = Field(True, description="Enable rule")
    severity: AlertSeverity = Field(..., description="Alert severity")
    conditions: Dict[str, Any] = Field(..., description="Rule conditions (JSON)")
    domain_pattern: Optional[str] = Field(None, max_length=255, description="Domain pattern (NULL = all)")
    cooldown_minutes: int = Field(60, ge=1, le=10080, description="Cooldown period in minutes")
    notify_email: bool = Field(True, description="Send email notifications")
    notify_teams: bool = Field(True, description="Send Teams notifications")
    notify_slack: bool = Field(False, description="Send Slack notifications")
    notify_webhook: bool = Field(False, description="Send webhook notifications")


class AlertRuleUpdate(BaseModel):
    """Schema for updating alert rule"""
    description: Optional[str] = None
    is_enabled: Optional[bool] = None
    severity: Optional[AlertSeverity] = None
    conditions: Optional[Dict[str, Any]] = None
    domain_pattern: Optional[str] = None
    cooldown_minutes: Optional[int] = Field(None, ge=1, le=10080)
    notify_email: Optional[bool] = None
    notify_teams: Optional[bool] = None
    notify_slack: Optional[bool] = None
    notify_webhook: Optional[bool] = None


class AlertRuleResponse(BaseModel):
    """Alert rule response"""
    id: UUID
    name: str
    description: Optional[str]
    alert_type: AlertType
    is_enabled: bool
    severity: AlertSeverity
    conditions: Dict[str, Any]
    domain_pattern: Optional[str]
    cooldown_minutes: int
    notify_email: bool
    notify_teams: bool
    notify_slack: bool
    notify_webhook: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID]

    class Config:
        from_attributes = True


# ==================== Alert Suppression Schemas ====================

class AlertSuppressionCreate(BaseModel):
    """Schema for creating alert suppression"""
    name: str = Field(..., min_length=1, max_length=255, description="Suppression name")
    description: Optional[str] = Field(None, description="Suppression description")
    is_active: bool = Field(True, description="Enable suppression")
    alert_type: Optional[AlertType] = Field(None, description="Alert type to suppress (NULL = all)")
    severity: Optional[AlertSeverity] = Field(None, description="Severity to suppress (NULL = all)")
    domain: Optional[str] = Field(None, max_length=255, description="Domain to suppress (NULL = all)")
    starts_at: Optional[datetime] = Field(None, description="Suppression start time")
    ends_at: Optional[datetime] = Field(None, description="Suppression end time")
    recurrence: Optional[Dict[str, Any]] = Field(None, description="Recurrence pattern (JSON)")


class AlertSuppressionUpdate(BaseModel):
    """Schema for updating alert suppression"""
    description: Optional[str] = None
    is_active: Optional[bool] = None
    alert_type: Optional[AlertType] = None
    severity: Optional[AlertSeverity] = None
    domain: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    recurrence: Optional[Dict[str, Any]] = None


class AlertSuppressionResponse(BaseModel):
    """Alert suppression response"""
    id: UUID
    name: str
    description: Optional[str]
    is_active: bool
    alert_type: Optional[AlertType]
    severity: Optional[AlertSeverity]
    domain: Optional[str]
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    recurrence: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID]

    class Config:
        from_attributes = True


# ==================== Bulk Operations ====================

class BulkAcknowledgeRequest(BaseModel):
    """Request to acknowledge multiple alerts"""
    alert_ids: List[UUID] = Field(..., min_items=1, max_items=100, description="Alert IDs to acknowledge")
    note: Optional[str] = Field(None, max_length=1000, description="Optional acknowledgement note")


class BulkResolveRequest(BaseModel):
    """Request to resolve multiple alerts"""
    alert_ids: List[UUID] = Field(..., min_items=1, max_items=100, description="Alert IDs to resolve")
    note: Optional[str] = Field(None, max_length=1000, description="Optional resolution note")


class BulkOperationResponse(BaseModel):
    """Response for bulk operations"""
    success_count: int = Field(..., description="Number of successful operations")
    failed_count: int = Field(..., description="Number of failed operations")
    errors: List[str] = Field(default_factory=list, description="Error messages")
