"""
MTA-STS Monitoring API routes.

Endpoints:
- GET /mta-sts/domains - List monitored domains
- POST /mta-sts/domains - Add domain to monitoring
- DELETE /mta-sts/domains/{domain} - Remove domain
- GET /mta-sts/check/{domain} - Check single domain
- POST /mta-sts/check-all - Check all domains
- GET /mta-sts/changes - Get change history
- GET /mta-sts/report/{domain} - Get detailed report
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.dependencies.auth import get_current_user, require_role
from app.services.mta_sts_service import MTASTSService, PolicyStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mta-sts", tags=["MTA-STS Monitoring"])


# ==================== Schemas ====================

class AddDomainRequest(BaseModel):
    domain: str = Field(..., description="Domain to monitor")


class MonitoredDomainResponse(BaseModel):
    id: UUID
    domain: str
    is_active: bool
    last_status: Optional[str] = None
    last_mode: Optional[str] = None
    last_policy_id: Optional[str] = None
    last_max_age: Optional[int] = None
    last_mx_hosts: Optional[List[str]] = None
    last_checked_at: Optional[str] = None
    last_change_at: Optional[str] = None
    consecutive_failures: int
    created_at: str


class STSRecordResponse(BaseModel):
    found: bool
    version: Optional[str] = None
    id: Optional[str] = None
    raw: Optional[str] = None


class STSPolicyResponse(BaseModel):
    found: bool
    mode: Optional[str] = None
    mx_hosts: List[str] = []
    max_age_seconds: Optional[int] = None
    max_age_days: Optional[int] = None
    raw: Optional[str] = None


class CheckResultResponse(BaseModel):
    domain: str
    has_record: bool
    has_policy: bool
    status: str
    mx_valid: bool
    record: STSRecordResponse
    policy: STSPolicyResponse
    issues: List[str]
    warnings: List[str]
    checked_at: str


class ChangeLogResponse(BaseModel):
    id: UUID
    domain: str
    change_type: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    detected_at: str


class ReportResponse(BaseModel):
    domain: str
    checked_at: str
    status: str
    has_mta_sts: bool
    record: dict
    policy: dict
    mx_validation: dict
    issues: List[str]
    warnings: List[str]
    recommendations: List[str]


# ==================== Routes ====================

@router.get(
    "/domains",
    response_model=List[MonitoredDomainResponse],
    status_code=status.HTTP_200_OK,
    summary="List monitored domains"
)
async def list_domains(
    active_only: bool = Query(True, description="Only show active domains"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all domains being monitored for MTA-STS."""
    service = MTASTSService(db)
    domains = service.get_domains(active_only=active_only)

    return [
        MonitoredDomainResponse(
            id=d.id,
            domain=d.domain,
            is_active=d.is_active,
            last_status=d.last_status,
            last_mode=d.last_mode,
            last_policy_id=d.last_policy_id,
            last_max_age=d.last_max_age,
            last_mx_hosts=d.last_mx_hosts.split(",") if d.last_mx_hosts else None,
            last_checked_at=d.last_checked_at.isoformat() if d.last_checked_at else None,
            last_change_at=d.last_change_at.isoformat() if d.last_change_at else None,
            consecutive_failures=d.consecutive_failures,
            created_at=d.created_at.isoformat(),
        )
        for d in domains
    ]


@router.post(
    "/domains",
    response_model=MonitoredDomainResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add domain to monitoring"
)
async def add_domain(
    request: AddDomainRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    Add a domain to MTA-STS monitoring.

    **Admin only.**

    Monitors:
    - MTA-STS DNS record (_mta-sts.domain)
    - MTA-STS policy file (https://mta-sts.domain/.well-known/mta-sts.txt)
    """
    service = MTASTSService(db)
    domain = service.add_domain(request.domain)

    return MonitoredDomainResponse(
        id=domain.id,
        domain=domain.domain,
        is_active=domain.is_active,
        last_status=domain.last_status,
        last_mode=domain.last_mode,
        last_policy_id=domain.last_policy_id,
        last_max_age=domain.last_max_age,
        last_mx_hosts=domain.last_mx_hosts.split(",") if domain.last_mx_hosts else None,
        last_checked_at=domain.last_checked_at.isoformat() if domain.last_checked_at else None,
        last_change_at=domain.last_change_at.isoformat() if domain.last_change_at else None,
        consecutive_failures=domain.consecutive_failures,
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
    current_user: User = Depends(require_role("admin")),
):
    """Remove a domain from MTA-STS monitoring. Admin only."""
    service = MTASTSService(db)

    if not service.remove_domain(domain):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )


@router.get(
    "/check/{domain}",
    response_model=CheckResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Check single domain"
)
async def check_domain(
    domain: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check MTA-STS configuration for a specific domain."""
    service = MTASTSService(db)
    check = service.check_domain(domain)

    return CheckResultResponse(
        domain=check.domain,
        has_record=check.has_record,
        has_policy=check.has_policy,
        status=check.status.value,
        mx_valid=check.mx_valid,
        record=STSRecordResponse(
            found=check.record is not None,
            version=check.record.version if check.record else None,
            id=check.record.id if check.record else None,
            raw=check.record.raw if check.record else None,
        ),
        policy=STSPolicyResponse(
            found=check.policy is not None,
            mode=check.policy.mode.value if check.policy else None,
            mx_hosts=check.policy.mx if check.policy else [],
            max_age_seconds=check.policy.max_age if check.policy else None,
            max_age_days=check.policy.max_age // 86400 if check.policy else None,
            raw=check.policy.raw if check.policy else None,
        ),
        issues=check.issues,
        warnings=check.warnings,
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
    current_user: User = Depends(require_role("admin")),
):
    """
    Check all monitored domains for MTA-STS status.

    **Admin only.**
    """
    service = MTASTSService(db)
    results = service.check_all_domains()

    summary = {
        "valid": 0,
        "invalid": 0,
        "missing": 0,
    }

    for check in results.values():
        if check.status == PolicyStatus.VALID:
            summary["valid"] += 1
        elif check.status == PolicyStatus.MISSING:
            summary["missing"] += 1
        else:
            summary["invalid"] += 1

    return {
        "domains_checked": len(results),
        "summary": summary,
        "results": {
            domain: {
                "status": check.status.value,
                "has_mta_sts": check.has_record and check.has_policy,
                "issues_count": len(check.issues),
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
    """Get MTA-STS change history."""
    service = MTASTSService(db)
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


@router.get(
    "/report/{domain}",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get detailed report"
)
async def get_report(
    domain: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a detailed MTA-STS report for a domain with recommendations."""
    service = MTASTSService(db)
    report = service.generate_report(domain)

    return ReportResponse(**report)
