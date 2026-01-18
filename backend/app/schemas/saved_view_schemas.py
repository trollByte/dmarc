"""
Saved View Schemas

Pydantic models for saved view API requests and responses.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class SavedViewFilters(BaseModel):
    """Schema for filter configuration"""
    domain: Optional[str] = None
    disposition: Optional[str] = None
    dateRange: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    sourceIp: Optional[str] = None
    minCount: Optional[int] = None
    dkimResult: Optional[str] = None
    spfResult: Optional[str] = None

    class Config:
        extra = "allow"  # Allow additional filter fields


class SavedViewDisplaySettings(BaseModel):
    """Schema for display settings"""
    sortBy: Optional[str] = None
    sortOrder: Optional[str] = None
    pageSize: Optional[int] = None
    visibleColumns: Optional[List[str]] = None
    chartType: Optional[str] = None

    class Config:
        extra = "allow"  # Allow additional display settings


class SavedViewCreate(BaseModel):
    """Schema for creating a saved view"""
    name: str = Field(..., min_length=1, max_length=100, description="View name")
    description: Optional[str] = Field(None, max_length=500, description="View description")
    icon: Optional[str] = Field(None, max_length=50, description="Icon identifier")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Filter configuration")
    display_settings: Optional[Dict[str, Any]] = Field(None, description="Display settings")
    is_shared: bool = Field(False, description="Whether view is shared with all users")
    is_default: bool = Field(False, description="Set as user's default view")


class SavedViewUpdate(BaseModel):
    """Schema for updating a saved view"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = Field(None, max_length=50)
    filters: Optional[Dict[str, Any]] = None
    display_settings: Optional[Dict[str, Any]] = None
    is_shared: Optional[bool] = None
    is_default: Optional[bool] = None


class SavedViewResponse(BaseModel):
    """Schema for saved view response"""
    id: UUID
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    filters: Dict[str, Any]
    display_settings: Optional[Dict[str, Any]] = None
    is_shared: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None
    user_id: UUID
    # Include username for shared views
    username: Optional[str] = None

    class Config:
        from_attributes = True


class SavedViewListResponse(BaseModel):
    """Schema for saved view list"""
    views: List[SavedViewResponse]
    total: int
