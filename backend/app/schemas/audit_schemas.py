"""
Pydantic schemas for Audit Logging.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class AuditLogEntry(BaseModel):
    """Single audit log entry"""
    id: UUID
    action: str
    category: str
    user_id: Optional[UUID] = None
    username: Optional[str] = None
    ip_address: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    description: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    request_method: Optional[str] = None
    request_path: Optional[str] = None
    response_status: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """List of audit logs with pagination"""
    logs: List[AuditLogEntry]
    total: int
    page: int
    page_size: int


class AuditLogStatsResponse(BaseModel):
    """Audit log statistics"""
    period_days: int
    total_events: int
    by_action: Dict[str, int]
    by_category: Dict[str, int]
    failed_logins: int


class AuditLogDetailResponse(BaseModel):
    """Detailed audit log entry with old/new values"""
    id: UUID
    action: str
    category: str
    user_id: Optional[UUID] = None
    username: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    description: Optional[str] = None
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    extra_data: Optional[Dict[str, Any]] = None
    request_method: Optional[str] = None
    request_path: Optional[str] = None
    response_status: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True
