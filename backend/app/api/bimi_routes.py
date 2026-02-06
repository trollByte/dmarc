"""
BIMI (Brand Indicators for Message Identification) API routes.

Endpoints:
- GET /bimi/domains - List monitored domains
- POST /bimi/domains - Add domain to monitoring
- DELETE /bimi/domains/{domain} - Remove domain
- GET /bimi/check/{domain} - Check single domain
- POST /bimi/check-all - Check all domains
- GET /bimi/changes - Get change history
- POST /bimi/generate - Generate BIMI record
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.dependencies.auth import get_current_user, require_role
from app.services.bimi_service import BIMIService, BIMIStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bimi", tags=["BIMI"])


# ==================== Schemas ====================

class AddDomainRequest(BaseModel):
    domain: str = Field(..., description="Domain to monitor")


class BIMIDomainResponse(BaseModel):
    id: UUID
    domain: str
    is_active: bool
    has_bimi_record: bool
    logo_url: Optional[str]
    authority_url: Optional[str]
    last_status: Optional[str]
    dmarc_compliant: bool
    logo_valid: bool
    vmc_valid: Optional[bool]
    last_checked_at: Optional[str]
    last_change_at: Optional[str]
    created_at: str


class LogoValidationResponse(BaseModel):
    url: str
    accessible: bool
    content_type: Optional[str]
    format: str
    size_bytes: int
    is_valid: bool
    issues: List[str]


class VMCValidationResponse(BaseModel):
    url: str
    accessible: bool
    has_certificate: bool
    is_valid: bool
    issuer: Optional[str]
    expires_at: Optional[str]
    issues: List[str]


class BIMIRecordResponse(BaseModel):
    version: str
    logo_url: Optional[str]
    authority_url: Optional[str]
    raw: str


class BIMICheckResponse(BaseModel):
    domain: str
    status: str
    has_record: bool
    record: Optional[BIMIRecordResponse]
    dmarc_compliant: bool
    dmarc_policy: Optional[str]
    logo_validation: Optional[LogoValidationResponse]
    vmc_validation: Optional[VMCValidationResponse]
    issues: List[str]
    warnings: List[str]
    recommendations: List[str]
    checked_at: str


class ChangeLogResponse(BaseModel):
    id: UUID
    domain: str
    change_type: str
    old_value: Optional[str]
    new_value: Optional[str]
    detected_at: str


class GenerateRecordRequest(BaseModel):
    domain: str
    logo_url: str = Field(..., description="HTTPS URL to SVG P/S logo")
    authority_url: Optional[str] = Field(None, description="HTTPS URL to VMC certificate")
    selector: str = Field(default="default", description="BIMI selector")


class GenerateRecordResponse(BaseModel):
    domain: str
    record_name: str
    record_type: str
    record_value: str
    ttl: int


# ==================== Routes ====================

@router.get(
    "/domains",
    response_model=List[BIMIDomainResponse],
    status_code=status.HTTP_200_OK,
    summary="List monitored domains"
)
async def list_domains(
    active_only: bool = Query(True, description="Only show active domains"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all domains being monitored for BIMI."""
    service = BIMIService(db)
    domains = service.get_domains(active_only=active_only)

    return [
        BIMIDomainResponse(
            id=d.id,
            domain=d.domain,
            is_active=d.is_active,
            has_bimi_record=d.has_bimi_record,
            logo_url=d.logo_url,
            authority_url=d.authority_url,
            last_status=d.last_status,
            dmarc_compliant=d.dmarc_compliant,
            logo_valid=d.logo_valid,
            vmc_valid=d.vmc_valid,
            last_checked_at=d.last_checked_at.isoformat() if d.last_checked_at else None,
            last_change_at=d.last_change_at.isoformat() if d.last_change_at else None,
            created_at=d.created_at.isoformat(),
        )
        for d in domains
    ]


@router.post(
    "/domains",
    response_model=BIMIDomainResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add domain to monitoring"
)
async def add_domain(
    request: AddDomainRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Add a domain to BIMI monitoring.

    **Admin only.**

    Checks:
    - BIMI DNS record (default._bimi.domain)
    - DMARC policy compliance
    - Logo accessibility and format
    - VMC certificate validity
    """
    service = BIMIService(db)
    domain = service.add_domain(request.domain)

    return BIMIDomainResponse(
        id=domain.id,
        domain=domain.domain,
        is_active=domain.is_active,
        has_bimi_record=domain.has_bimi_record,
        logo_url=domain.logo_url,
        authority_url=domain.authority_url,
        last_status=domain.last_status,
        dmarc_compliant=domain.dmarc_compliant,
        logo_valid=domain.logo_valid,
        vmc_valid=domain.vmc_valid,
        last_checked_at=domain.last_checked_at.isoformat() if domain.last_checked_at else None,
        last_change_at=domain.last_change_at.isoformat() if domain.last_change_at else None,
        created_at=domain.created_at.isoformat(),
    )


@router.delete(
    "/domains/{domain}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove domain from monitoring"
)
async def remove_domain(
    domain: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Remove a domain from BIMI monitoring. Admin only."""
    service = BIMIService(db)

    if not service.remove_domain(domain):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )


@router.get(
    "/check/{domain}",
    response_model=BIMICheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Check BIMI for domain"
)
async def check_domain(
    domain: str,
    selector: str = Query("default", description="BIMI selector"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check BIMI configuration for a domain.

    Validates:
    - BIMI DNS record
    - DMARC policy (must be quarantine or reject)
    - Logo format (must be SVG P/S)
    - VMC certificate (optional)
    """
    service = BIMIService(db)
    check = service.check_domain(domain, selector)
    recommendations = service.get_recommendations(check)

    return BIMICheckResponse(
        domain=check.domain,
        status=check.status.value,
        has_record=check.has_record,
        record=BIMIRecordResponse(
            version=check.record.version,
            logo_url=check.record.logo_url,
            authority_url=check.record.authority_url,
            raw=check.record.raw,
        ) if check.record else None,
        dmarc_compliant=check.dmarc_compliant,
        dmarc_policy=check.dmarc_policy,
        logo_validation=LogoValidationResponse(
            url=check.logo_validation.url,
            accessible=check.logo_validation.accessible,
            content_type=check.logo_validation.content_type,
            format=check.logo_validation.format.value,
            size_bytes=check.logo_validation.size_bytes,
            is_valid=check.logo_validation.is_valid,
            issues=check.logo_validation.issues,
        ) if check.logo_validation else None,
        vmc_validation=VMCValidationResponse(
            url=check.vmc_validation.url,
            accessible=check.vmc_validation.accessible,
            has_certificate=check.vmc_validation.has_certificate,
            is_valid=check.vmc_validation.is_valid,
            issuer=check.vmc_validation.issuer,
            expires_at=check.vmc_validation.expires_at.isoformat() if check.vmc_validation.expires_at else None,
            issues=check.vmc_validation.issues,
        ) if check.vmc_validation else None,
        issues=check.issues,
        warnings=check.warnings,
        recommendations=recommendations,
        checked_at=check.checked_at.isoformat(),
    )


@router.post(
    "/check-all",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Check all domains"
)
async def check_all_domains(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Check all monitored domains for BIMI status.

    **Admin only.**
    """
    service = BIMIService(db)
    results = service.check_all_domains()

    summary = {
        "valid": 0,
        "partial": 0,
        "invalid": 0,
        "missing": 0,
    }

    for check in results.values():
        summary[check.status.value] += 1

    return {
        "domains_checked": len(results),
        "summary": summary,
        "results": {
            domain: {
                "status": check.status.value,
                "has_record": check.has_record,
                "dmarc_compliant": check.dmarc_compliant,
                "logo_valid": check.logo_validation.is_valid if check.logo_validation else False,
                "vmc_valid": check.vmc_validation.is_valid if check.vmc_validation else None,
            }
            for domain, check in results.items()
        }
    }


@router.get(
    "/changes",
    response_model=List[ChangeLogResponse],
    status_code=status.HTTP_200_OK,
    summary="Get change history"
)
async def get_changes(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    days: int = Query(30, ge=1, le=365, description="Days to look back"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get BIMI change history."""
    service = BIMIService(db)
    changes = service.get_changes(domain=domain, days=days, limit=limit)

    return [
        ChangeLogResponse(
            id=c.id,
            domain=c.domain,
            change_type=c.change_type,
            old_value=c.old_value,
            new_value=c.new_value,
            detected_at=c.detected_at.isoformat(),
        )
        for c in changes
    ]


@router.post(
    "/generate",
    response_model=GenerateRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate BIMI record"
)
async def generate_record(
    request: GenerateRecordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a BIMI DNS record.

    Example:
    ```json
    {
        "domain": "example.com",
        "logo_url": "https://example.com/logo.svg",
        "authority_url": "https://example.com/vmc.pem"
    }
    ```
    """
    service = BIMIService(db)
    record = service.generate_bimi_record(
        domain=request.domain,
        logo_url=request.logo_url,
        authority_url=request.authority_url,
        selector=request.selector,
    )

    return GenerateRecordResponse(**record)
