"""
Pydantic schemas for DMARC/SPF/DKIM record generation.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class PolicyType(str, Enum):
    NONE = "none"
    QUARANTINE = "quarantine"
    REJECT = "reject"


class AlignmentType(str, Enum):
    RELAXED = "r"
    STRICT = "s"


class DMARCGenerateRequest(BaseModel):
    """Request to generate a DMARC record"""
    domain: str = Field(..., description="Domain name")
    policy: PolicyType = Field(default=PolicyType.NONE, description="DMARC policy")
    subdomain_policy: Optional[PolicyType] = Field(None, description="Subdomain policy")
    pct: int = Field(default=100, ge=1, le=100, description="Percentage of messages")
    rua: Optional[List[str]] = Field(None, description="Aggregate report recipients")
    ruf: Optional[List[str]] = Field(None, description="Forensic report recipients")
    adkim: AlignmentType = Field(default=AlignmentType.RELAXED, description="DKIM alignment")
    aspf: AlignmentType = Field(default=AlignmentType.RELAXED, description="SPF alignment")


class SPFGenerateRequest(BaseModel):
    """Request to generate an SPF record"""
    domain: str = Field(..., description="Domain name")
    include: Optional[List[str]] = Field(None, description="Domains to include")
    ip4: Optional[List[str]] = Field(None, description="IPv4 addresses/ranges")
    ip6: Optional[List[str]] = Field(None, description="IPv6 addresses/ranges")
    a: bool = Field(default=False, description="Include A record")
    mx: bool = Field(default=False, description="Include MX records")
    all_mechanism: str = Field(default="~all", description="All mechanism (~all, -all, ?all)")


class DNSRecordResponse(BaseModel):
    """Generated DNS record"""
    domain: str
    record_name: str
    record_type: str
    record_value: str
    ttl: int = 3600


class ValidationResponse(BaseModel):
    """Record validation result"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]


class ValidateRecordRequest(BaseModel):
    """Request to validate a record"""
    record_type: str = Field(..., description="Type: dmarc or spf")
    record_value: str = Field(..., description="Record value to validate")


class PolicyRecommendationRequest(BaseModel):
    """Request for policy recommendation"""
    has_existing_dmarc: bool = Field(default=False)
    current_policy: Optional[str] = Field(None)
    pass_rate: float = Field(default=0.0, ge=0, le=100)
    days_monitoring: int = Field(default=0, ge=0)


class PolicyRecommendationResponse(BaseModel):
    """Policy recommendation"""
    recommended_policy: str
    pct: int
    reasoning: str
    next_steps: List[str]


class WizardStepResponse(BaseModel):
    """Wizard step definition"""
    step: int
    title: str
    description: str
    fields: List[str]
    options: Optional[Dict[str, Any]] = None
    advanced: bool = False
