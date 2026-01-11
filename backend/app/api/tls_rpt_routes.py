"""
TLS-RPT (TLS Reporting) API routes.

Endpoints:
- POST /tls-rpt/upload - Upload TLS-RPT report
- GET /tls-rpt/reports - List reports
- GET /tls-rpt/reports/{id} - Get single report
- GET /tls-rpt/failures - Get failure summaries
- GET /tls-rpt/stats/{domain} - Get domain statistics
- GET /tls-rpt/trends - Get failure trends
- GET /tls-rpt/check/{domain} - Check TLS-RPT DNS record
- POST /tls-rpt/generate - Generate TLS-RPT record
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.dependencies.auth import get_current_user, require_role
from app.services.tls_rpt_service import TLSRPTService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tls-rpt", tags=["TLS-RPT"])


# ==================== Schemas ====================

class ReportSummary(BaseModel):
    id: UUID
    report_id: str
    organization_name: str
    policy_domain: str
    policy_type: str
    date_range_begin: str
    date_range_end: str
    successful_sessions: int
    failed_sessions: int
    received_at: str


class ReportDetail(BaseModel):
    id: UUID
    report_id: str
    organization_name: str
    contact_info: Optional[str]
    policy_domain: str
    policy_type: str
    date_range_begin: str
    date_range_end: str
    successful_sessions: int
    failed_sessions: int
    policies: List[dict]
    failure_details: List[dict]
    received_at: str
    source_ip: Optional[str]
    filename: Optional[str]


class FailureSummaryResponse(BaseModel):
    id: UUID
    policy_domain: str
    result_type: str
    receiving_mx_hostname: Optional[str]
    failure_count: int
    report_count: int
    first_seen: str
    last_seen: str


class DomainStatsResponse(BaseModel):
    domain: str
    period_days: int
    report_count: int
    total_sessions: int
    successful_sessions: int
    failed_sessions: int
    success_rate: float
    failures_by_type: dict
    unique_reporters: int


class TrendDataPoint(BaseModel):
    date: str
    successful_sessions: int
    failed_sessions: int
    report_count: int


class DNSCheckResponse(BaseModel):
    domain: str
    has_record: bool
    record: Optional[str]
    rua: List[str]
    issues: List[str]


class GenerateRecordRequest(BaseModel):
    domain: str
    rua: List[str] = Field(..., description="Reporting URIs (mailto: or https:)")


class GenerateRecordResponse(BaseModel):
    domain: str
    record_name: str
    record_type: str
    record_value: str
    ttl: int


# ==================== Routes ====================

@router.post(
    "/upload",
    response_model=ReportSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Upload TLS-RPT report"
)
async def upload_report(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a TLS-RPT report.

    Accepts:
    - JSON files
    - Gzipped JSON files

    Reports are deduplicated by content hash.
    """
    content = await file.read()

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file"
        )

    service = TLSRPTService(db)

    try:
        report = service.store_report(
            data=content,
            filename=file.filename,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return ReportSummary(
        id=report.id,
        report_id=report.report_id,
        organization_name=report.organization_name,
        policy_domain=report.policy_domain,
        policy_type=report.policy_type,
        date_range_begin=report.date_range_begin.isoformat(),
        date_range_end=report.date_range_end.isoformat(),
        successful_sessions=report.successful_session_count,
        failed_sessions=report.failed_session_count,
        received_at=report.received_at.isoformat(),
    )


@router.get(
    "/reports",
    response_model=List[ReportSummary],
    status_code=status.HTTP_200_OK,
    summary="List TLS-RPT reports"
)
async def list_reports(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    days: int = Query(30, ge=1, le=365, description="Days to look back"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get TLS-RPT reports."""
    service = TLSRPTService(db)
    reports = service.get_reports(domain=domain, days=days, limit=limit)

    return [
        ReportSummary(
            id=r.id,
            report_id=r.report_id,
            organization_name=r.organization_name,
            policy_domain=r.policy_domain,
            policy_type=r.policy_type,
            date_range_begin=r.date_range_begin.isoformat(),
            date_range_end=r.date_range_end.isoformat(),
            successful_sessions=r.successful_session_count,
            failed_sessions=r.failed_session_count,
            received_at=r.received_at.isoformat(),
        )
        for r in reports
    ]


@router.get(
    "/reports/{report_id}",
    response_model=ReportDetail,
    status_code=status.HTTP_200_OK,
    summary="Get report details"
)
async def get_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed TLS-RPT report."""
    from app.services.tls_rpt_service import TLSReport

    report = db.query(TLSReport).filter(TLSReport.id == report_id).first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )

    return ReportDetail(
        id=report.id,
        report_id=report.report_id,
        organization_name=report.organization_name,
        contact_info=report.contact_info,
        policy_domain=report.policy_domain,
        policy_type=report.policy_type,
        date_range_begin=report.date_range_begin.isoformat(),
        date_range_end=report.date_range_end.isoformat(),
        successful_sessions=report.successful_session_count,
        failed_sessions=report.failed_session_count,
        policies=report.policies or [],
        failure_details=report.failure_details or [],
        received_at=report.received_at.isoformat(),
        source_ip=report.source_ip,
        filename=report.filename,
    )


@router.get(
    "/failures",
    response_model=List[FailureSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get failure summaries"
)
async def get_failures(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    result_type: Optional[str] = Query(None, description="Filter by result type"),
    days: int = Query(30, ge=1, le=365, description="Days to look back"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get aggregated TLS failure summaries."""
    service = TLSRPTService(db)
    failures = service.get_failures(
        domain=domain,
        result_type=result_type,
        days=days,
    )

    return [
        FailureSummaryResponse(
            id=f.id,
            policy_domain=f.policy_domain,
            result_type=f.result_type,
            receiving_mx_hostname=f.receiving_mx_hostname,
            failure_count=f.failure_count,
            report_count=f.report_count,
            first_seen=f.first_seen.isoformat(),
            last_seen=f.last_seen.isoformat(),
        )
        for f in failures
    ]


@router.get(
    "/stats/{domain}",
    response_model=DomainStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get domain statistics"
)
async def get_domain_stats(
    domain: str,
    days: int = Query(30, ge=1, le=365, description="Days to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get TLS statistics for a domain."""
    service = TLSRPTService(db)
    stats = service.get_domain_stats(domain, days=days)

    return DomainStatsResponse(**stats)


@router.get(
    "/trends",
    response_model=List[TrendDataPoint],
    status_code=status.HTTP_200_OK,
    summary="Get failure trends"
)
async def get_trends(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    days: int = Query(30, ge=1, le=90, description="Days to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get daily TLS failure trends."""
    service = TLSRPTService(db)
    trends = service.get_failure_trends(domain=domain, days=days)

    return [TrendDataPoint(**t) for t in trends]


@router.get(
    "/check/{domain}",
    response_model=DNSCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Check TLS-RPT DNS record"
)
async def check_dns_record(
    domain: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if a domain has a TLS-RPT DNS record."""
    service = TLSRPTService(db)
    result = service.check_tlsrpt_record(domain)

    return DNSCheckResponse(**result)


@router.post(
    "/generate",
    response_model=GenerateRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate TLS-RPT record"
)
async def generate_record(
    request: GenerateRecordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a TLS-RPT DNS record.

    Example:
    ```json
    {
        "domain": "example.com",
        "rua": ["mailto:tlsrpt@example.com"]
    }
    ```
    """
    service = TLSRPTService(db)
    record = service.generate_tlsrpt_record(
        domain=request.domain,
        rua=request.rua,
    )

    return GenerateRecordResponse(**record)
