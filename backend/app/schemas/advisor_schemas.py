"""
Pydantic schemas for Policy Advisor endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class RecommendationType(str, Enum):
    """Types of recommendations"""
    POLICY_UPGRADE = "policy_upgrade"
    POLICY_DOWNGRADE = "policy_downgrade"
    NEW_SENDER = "new_sender"
    SPF_ISSUE = "spf_issue"
    DKIM_ISSUE = "dkim_issue"
    ALIGNMENT_ISSUE = "alignment_issue"
    LOW_VOLUME = "low_volume"
    HIGH_FAILURE = "high_failure"


class RecommendationPriority(str, Enum):
    """Priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class RecommendationResponse(BaseModel):
    """A single recommendation"""
    type: RecommendationType
    priority: RecommendationPriority
    domain: str
    title: str
    description: str
    current_state: Dict[str, Any]
    recommended_action: str
    impact: str
    confidence: float = Field(ge=0, le=1)


class DomainHealthResponse(BaseModel):
    """Health score for a domain"""
    domain: str
    overall_score: int = Field(ge=0, le=100)
    pass_rate: float
    spf_alignment_rate: float
    dkim_alignment_rate: float
    current_policy: str
    recommended_policy: str
    total_emails: int
    total_sources: int
    issues: List[str]
    grade: str


class DomainStatsResponse(BaseModel):
    """Detailed statistics for a domain"""
    domain: str
    days_analyzed: int
    total_emails: int
    unique_sources: int
    current_policy: str
    dkim_pass_rate: float
    spf_pass_rate: float
    dmarc_pass_rate: float
    both_pass_rate: float
    both_fail_rate: float
    report_count: int


class FailingSenderResponse(BaseModel):
    """A sender that's failing authentication"""
    source_ip: str
    total_emails: int
    dkim_pass: int
    spf_pass: int
    both_fail: int
    failure_rate: float
    dkim_pass_rate: float
    spf_pass_rate: float


class OverallHealthResponse(BaseModel):
    """Overall health across all domains"""
    total_domains: int
    analyzed_domains: int
    overall_score: float
    grade: str
    total_emails: int
    total_sources: int
    policy_breakdown: Dict[str, int]
    grade_breakdown: Dict[str, int]
    domains_at_reject: int
    domains_needing_upgrade: int


class RecommendationsListResponse(BaseModel):
    """List of recommendations"""
    total: int
    recommendations: List[RecommendationResponse]


class DomainListResponse(BaseModel):
    """List of domains with health scores"""
    total: int
    domains: List[DomainHealthResponse]
