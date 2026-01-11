"""
Pydantic schemas for Data Retention.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

from app.models import RetentionTarget


class RetentionPolicyCreate(BaseModel):
    """Create a new retention policy"""
    name: str = Field(..., min_length=1, max_length=100, description="Policy name")
    target: RetentionTarget = Field(..., description="Target data type")
    retention_days: int = Field(..., ge=1, le=3650, description="Days to retain data")
    description: Optional[str] = Field(None, max_length=500, description="Policy description")
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional filters")
    is_enabled: bool = Field(True, description="Whether policy is enabled")


class RetentionPolicyUpdate(BaseModel):
    """Update an existing retention policy"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    retention_days: Optional[int] = Field(None, ge=1, le=3650)
    description: Optional[str] = Field(None, max_length=500)
    filters: Optional[Dict[str, Any]] = None
    is_enabled: Optional[bool] = None


class RetentionPolicyResponse(BaseModel):
    """Retention policy response"""
    id: UUID
    name: str
    target: str
    retention_days: int
    description: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    is_enabled: bool
    last_run_at: Optional[datetime] = None
    last_run_deleted: Optional[int] = None
    total_deleted: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RetentionLogResponse(BaseModel):
    """Retention execution log"""
    id: UUID
    policy_id: Optional[UUID] = None
    policy_name: str
    target: str
    retention_days: int
    records_deleted: int
    cutoff_date: datetime
    success: bool
    error_message: Optional[str] = None
    executed_at: datetime
    duration_seconds: Optional[int] = None

    class Config:
        from_attributes = True


class RetentionPreviewResponse(BaseModel):
    """Preview of what would be deleted"""
    target: str
    retention_days: int
    cutoff_date: str
    records_to_delete: int


class RetentionStatsResponse(BaseModel):
    """Retention statistics"""
    policies: Dict[str, int]
    total_records_deleted: int
    data_sizes: Dict[str, int]


class RetentionExecuteResponse(BaseModel):
    """Response after executing retention policies"""
    executed: int
    total_deleted: int
    logs: List[RetentionLogResponse]
