"""
DMARC/SPF Record Generator API routes.

Endpoints:
- POST /generator/dmarc - Generate DMARC record
- POST /generator/spf - Generate SPF record
- POST /generator/validate - Validate a record
- POST /generator/recommend - Get policy recommendation
- GET /generator/wizard - Get wizard steps
"""

import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.dependencies.auth import get_current_user
from app.services.dmarc_generator import (
    DMARCGeneratorService,
    DMARCPolicy,
    AlignmentMode,
)
from app.services.spf_flattening import SPFFlatteningService
from app.schemas.generator_schemas import (
    DMARCGenerateRequest,
    SPFGenerateRequest,
    DNSRecordResponse,
    ValidationResponse,
    ValidateRecordRequest,
    PolicyRecommendationRequest,
    PolicyRecommendationResponse,
    WizardStepResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generator", tags=["Record Generator"])


@router.post(
    "/dmarc",
    response_model=DNSRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate DMARC record"
)
async def generate_dmarc(
    request: DMARCGenerateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Generate a DMARC DNS TXT record.

    **Example:**
    ```json
    {
        "domain": "example.com",
        "policy": "quarantine",
        "pct": 100,
        "rua": ["dmarc@example.com"]
    }
    ```

    **Returns:**
    ```json
    {
        "domain": "example.com",
        "record_name": "_dmarc.example.com",
        "record_type": "TXT",
        "record_value": "v=DMARC1; p=quarantine; rua=mailto:dmarc@example.com"
    }
    ```
    """
    service = DMARCGeneratorService()

    # Convert enum types
    policy = DMARCPolicy(request.policy.value)
    subdomain_policy = DMARCPolicy(request.subdomain_policy.value) if request.subdomain_policy else None
    adkim = AlignmentMode(request.adkim.value)
    aspf = AlignmentMode(request.aspf.value)

    record = service.generate_dmarc(
        domain=request.domain,
        policy=policy,
        subdomain_policy=subdomain_policy,
        pct=request.pct,
        rua=request.rua,
        ruf=request.ruf,
        adkim=adkim,
        aspf=aspf,
    )

    return DNSRecordResponse(
        domain=record.domain,
        record_name=record.record_name,
        record_type=record.record_type,
        record_value=record.record_value,
        ttl=record.ttl,
    )


@router.post(
    "/spf",
    response_model=DNSRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate SPF record"
)
async def generate_spf(
    request: SPFGenerateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Generate an SPF DNS TXT record.

    **Example:**
    ```json
    {
        "domain": "example.com",
        "include": ["_spf.google.com"],
        "mx": true,
        "all_mechanism": "-all"
    }
    ```

    **Returns:**
    ```json
    {
        "domain": "example.com",
        "record_name": "example.com",
        "record_type": "TXT",
        "record_value": "v=spf1 mx include:_spf.google.com -all"
    }
    ```
    """
    service = DMARCGeneratorService()

    record = service.generate_spf(
        domain=request.domain,
        include=request.include,
        ip4=request.ip4,
        ip6=request.ip6,
        a=request.a,
        mx=request.mx,
        all_mechanism=request.all_mechanism,
    )

    return DNSRecordResponse(
        domain=record.domain,
        record_name=record.record_name,
        record_type=record.record_type,
        record_value=record.record_value,
        ttl=record.ttl,
    )


@router.post(
    "/validate",
    response_model=ValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate a record"
)
async def validate_record(
    request: ValidateRecordRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Validate a DMARC or SPF record.

    **Example:**
    ```json
    {
        "record_type": "dmarc",
        "record_value": "v=DMARC1; p=none; rua=mailto:dmarc@example.com"
    }
    ```

    **Returns:**
    - is_valid: Whether the record is valid
    - errors: Critical issues that must be fixed
    - warnings: Issues that should be addressed
    - suggestions: Optional improvements
    """
    service = DMARCGeneratorService()

    if request.record_type.lower() == "dmarc":
        result = service.validate_dmarc(request.record_value)
    elif request.record_type.lower() == "spf":
        result = service.validate_spf(request.record_value)
    else:
        return ValidationResponse(
            is_valid=False,
            errors=[f"Unknown record type: {request.record_type}"],
            warnings=[],
            suggestions=[],
        )

    return ValidationResponse(
        is_valid=result.is_valid,
        errors=result.errors,
        warnings=result.warnings,
        suggestions=result.suggestions,
    )


@router.post(
    "/recommend",
    response_model=PolicyRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get policy recommendation"
)
async def get_recommendation(
    request: PolicyRecommendationRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Get DMARC policy recommendation based on current state.

    **Example:**
    ```json
    {
        "has_existing_dmarc": true,
        "current_policy": "none",
        "pass_rate": 98.5,
        "days_monitoring": 30
    }
    ```

    **Returns:**
    - recommended_policy: Suggested policy
    - pct: Suggested percentage
    - reasoning: Why this is recommended
    - next_steps: Action items
    """
    service = DMARCGeneratorService()

    result = service.get_policy_recommendation(
        has_existing_dmarc=request.has_existing_dmarc,
        current_policy=request.current_policy,
        pass_rate=request.pass_rate,
        days_monitoring=request.days_monitoring,
    )

    return PolicyRecommendationResponse(**result)


@router.get(
    "/wizard",
    response_model=list[WizardStepResponse],
    status_code=status.HTTP_200_OK,
    summary="Get wizard steps"
)
async def get_wizard_steps(
    current_user: User = Depends(get_current_user),
):
    """
    Get the wizard step definitions for the UI.

    Returns the configuration for a multi-step wizard
    to guide users through DMARC setup.
    """
    service = DMARCGeneratorService()
    steps = service.generate_wizard_steps()

    return [WizardStepResponse(**step) for step in steps]


# ==================== SPF Flattening ====================

from pydantic import BaseModel
from typing import Optional

class SPFAnalyzeRequest(BaseModel):
    domain: str

class SPFFlattenRequest(BaseModel):
    domain: str
    keep_includes: Optional[list[str]] = None

class SPFAnalysisResponse(BaseModel):
    domain: str
    original_record: str
    dns_lookups: int
    exceeds_limit: bool
    includes: list[str]
    ip4_addresses: list[str]
    ip6_addresses: list[str]
    errors: list[str]
    warnings: list[str]

class SPFFlattenedResponse(BaseModel):
    domain: str
    original_record: str
    original_lookups: int
    flattened_record: str
    flattened_lookups: int
    ip4_addresses: list[str]
    ip6_addresses: list[str]
    unresolved_includes: list[str]
    warnings: list[str]


@router.post(
    "/spf/analyze",
    response_model=SPFAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze SPF record"
)
async def analyze_spf(
    request: SPFAnalyzeRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Analyze an SPF record for a domain.

    Returns details about DNS lookups, includes, and potential issues.
    """
    service = SPFFlatteningService()
    result = service.analyze_spf(request.domain)

    return SPFAnalysisResponse(
        domain=result.domain,
        original_record=result.original_record,
        dns_lookups=result.dns_lookups,
        exceeds_limit=result.exceeds_limit,
        includes=result.includes,
        ip4_addresses=result.ip4_addresses,
        ip6_addresses=result.ip6_addresses,
        errors=result.errors,
        warnings=result.warnings,
    )


@router.post(
    "/spf/flatten",
    response_model=SPFFlattenedResponse,
    status_code=status.HTTP_200_OK,
    summary="Flatten SPF record"
)
async def flatten_spf(
    request: SPFFlattenRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Flatten an SPF record by resolving includes to IP addresses.

    This reduces DNS lookups by replacing include mechanisms
    with the actual IP addresses they resolve to.

    **Note:** Flattened records need periodic updates as IPs may change.
    """
    service = SPFFlatteningService()
    result = service.flatten_spf(
        domain=request.domain,
        keep_includes=request.keep_includes,
    )

    return SPFFlattenedResponse(
        domain=result.domain,
        original_record=result.original_record,
        original_lookups=result.original_lookups,
        flattened_record=result.flattened_record,
        flattened_lookups=result.flattened_lookups,
        ip4_addresses=result.ip4_addresses,
        ip6_addresses=result.ip6_addresses,
        unresolved_includes=result.unresolved_includes,
        warnings=result.warnings,
    )
