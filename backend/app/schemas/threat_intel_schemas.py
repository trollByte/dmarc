"""
Pydantic schemas for Threat Intelligence endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ThreatLevel(str, Enum):
    """Threat level classification"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    CLEAN = "clean"
    UNKNOWN = "unknown"


class ThreatInfoResponse(BaseModel):
    """Threat intelligence for an IP"""
    ip_address: str
    threat_level: ThreatLevel
    abuse_score: int = Field(ge=0, le=100)
    total_reports: int
    last_reported: Optional[datetime] = None
    is_whitelisted: bool
    is_tor: bool
    is_public: bool
    isp: Optional[str] = None
    domain: Optional[str] = None
    country_code: Optional[str] = None
    usage_type: Optional[str] = None
    categories: List[str] = []
    cached_at: datetime
    source: str


class ThreatCheckRequest(BaseModel):
    """Request to check IP threat level"""
    ip_address: str
    use_cache: bool = True


class ThreatBulkCheckRequest(BaseModel):
    """Request to check multiple IPs"""
    ip_addresses: List[str] = Field(..., min_length=1, max_length=100)
    use_cache: bool = True


class ThreatBulkCheckResponse(BaseModel):
    """Response from bulk IP check"""
    total: int
    checked: int
    results: Dict[str, Optional[ThreatInfoResponse]]
    summary: Dict[str, int]  # Count by threat level


class ThreatCacheStatsResponse(BaseModel):
    """Threat intel cache statistics"""
    total_entries: int
    active_entries: int
    expired_entries: int
    by_threat_level: Dict[str, int]
    api_configured: bool


class HighThreatIPResponse(BaseModel):
    """High threat IP from cache"""
    ip_address: str
    threat_level: str
    abuse_score: int
    total_reports: int
    last_reported: Optional[datetime] = None
    isp: Optional[str] = None
    country_code: Optional[str] = None
    categories: List[str] = []
    created_at: datetime


class EnrichedAnomalyResponse(BaseModel):
    """Anomaly detection result enriched with threat intel"""
    ip_address: str
    anomaly_score: float
    features: Dict[str, Any]
    threat_info: Optional[ThreatInfoResponse] = None
    combined_risk_score: float = Field(ge=0, le=100)
    risk_factors: List[str] = []
