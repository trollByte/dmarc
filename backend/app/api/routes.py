"""
API routes for DMARC reporting and rollups
"""
from fastapi import APIRouter, Depends, Query, UploadFile, File, Security, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case
from typing import Optional, List
from datetime import datetime
import logging
import io

from app.database import get_db
from app.models import DmarcReport, DmarcRecord
from app.middleware.auth import get_api_key
from app.middleware.rate_limit import limiter
from app.schemas.api_schemas import (
    DomainsListResponse,
    DomainInfo,
    ReportsListResponse,
    ReportDetail,
    SummaryStats,
    SourceIPListResponse,
    SourceIPStats,
    AlignmentStats,
    HealthCheckResponse,
    TimelineStats,
    TimelineListResponse,
    IngestTriggerResponse,
    ProcessTriggerResponse,
    ConfigStatusResponse,
    CheckAlertsResponse,
    AlertConfigResponse,
    AlertDetail,
    UploadReportsResponse,
    UploadedFileDetail,
    RecordDetailResponse,
    ReportRecordsResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/healthz", response_model=HealthCheckResponse)
async def healthz():
    """
    Comprehensive health check endpoint

    Checks:
    - Database connectivity
    - Background scheduler status
    - File system access (logs and storage)
    """
    from app.database import check_db_connection
    from app.services.scheduler import get_scheduler
    from pathlib import Path

    db_connected = check_db_connection()

    # Check scheduler status
    scheduler = get_scheduler()
    scheduler_running = scheduler._started if scheduler else False

    # Check file system access
    try:
        settings = get_settings()
        logs_dir = Path(settings.log_dir)
        storage_dir = Path(settings.raw_reports_path)

        logs_accessible = logs_dir.exists() or logs_dir.parent.exists()
        storage_accessible = storage_dir.exists() or storage_dir.parent.exists()
        fs_status = "accessible" if (logs_accessible and storage_accessible) else "limited"
    except Exception:
        fs_status = "error"

    # Determine overall health
    is_healthy = db_connected and scheduler_running

    return HealthCheckResponse(
        status="healthy" if is_healthy else "unhealthy",
        service="DMARC Report Processor API",
        database="connected" if db_connected else "disconnected"
    )


@router.get("/api/config/status", response_model=ConfigStatusResponse)
async def config_status():
    """
    Get configuration status

    Returns information about email configuration and background jobs.
    """
    from app.config import get_settings
    from app.services.scheduler import get_scheduler

    settings = get_settings()
    scheduler = get_scheduler()

    # Check if email is configured
    email_configured = bool(
        settings.email_host and
        settings.email_user and
        settings.email_password
    )

    # Get scheduler status
    scheduler_running = scheduler._started if scheduler else False
    background_jobs = []
    if scheduler and scheduler_running:
        background_jobs = [job.id for job in scheduler.scheduler.get_jobs()]

    return ConfigStatusResponse(
        email_configured=email_configured,
        email_host=settings.email_host if email_configured else None,
        email_folder=settings.email_folder if email_configured else None,
        scheduler_running=scheduler_running,
        background_jobs=background_jobs
    )


@router.get("/api/domains", response_model=DomainsListResponse)
async def list_domains(db: Session = Depends(get_db)):
    """
    List all domains with report counts and date ranges
    """
    domains_query = db.query(
        DmarcReport.domain,
        func.count(DmarcReport.id).label('report_count'),
        func.min(DmarcReport.date_begin).label('earliest_report'),
        func.max(DmarcReport.date_end).label('latest_report')
    ).group_by(DmarcReport.domain).order_by(DmarcReport.domain).all()

    domains = [
        DomainInfo(
            domain=d.domain,
            report_count=d.report_count,
            earliest_report=d.earliest_report,
            latest_report=d.latest_report
        )
        for d in domains_query
    ]

    return DomainsListResponse(
        domains=domains,
        total=len(domains)
    )


@router.get("/api/reports", response_model=ReportsListResponse)
async def list_reports(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    start: Optional[datetime] = Query(None, description="Filter by start date"),
    end: Optional[datetime] = Query(None, description="Filter by end date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db)
):
    """
    List DMARC reports with optional filters and pagination
    """
    query = db.query(DmarcReport)

    # Apply filters
    if domain:
        query = query.filter(DmarcReport.domain == domain)
    if start:
        query = query.filter(DmarcReport.date_begin >= start)
    if end:
        query = query.filter(DmarcReport.date_end <= end)

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    reports = query.order_by(DmarcReport.date_end.desc()).offset(offset).limit(page_size).all()

    # Enhance reports with computed fields
    reports_data = []
    for report in reports:
        # Count records and total messages
        record_count = len(report.records)
        total_messages = sum(r.count for r in report.records)

        reports_data.append(ReportDetail(
            id=report.id,
            report_id=report.report_id,
            org_name=report.org_name,
            email=report.email,
            domain=report.domain,
            date_begin=report.date_begin,
            date_end=report.date_end,
            p=report.p,
            sp=report.sp,
            pct=report.pct,
            created_at=report.created_at,
            record_count=record_count,
            total_messages=total_messages
        ))

    return ReportsListResponse(
        reports=reports_data,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/api/reports/{report_id}", response_model=ReportDetail)
async def get_report(
    report_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a single DMARC report by ID with full details
    """
    report = db.query(DmarcReport).filter(DmarcReport.id == report_id).first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Count records and total messages
    record_count = len(report.records)
    total_messages = sum(r.count for r in report.records)

    return ReportDetail(
        id=report.id,
        report_id=report.report_id,
        org_name=report.org_name,
        email=report.email,
        domain=report.domain,
        date_begin=report.date_begin,
        date_end=report.date_end,
        p=report.p,
        sp=report.sp,
        pct=report.pct,
        created_at=report.created_at,
        record_count=record_count,
        total_messages=total_messages,
        # Frontend compatibility fields
        policy_p=report.p,
        policy_sp=report.sp,
        policy_pct=report.pct,
        policy_adkim=report.adkim,
        policy_aspf=report.aspf,
        received_at=report.created_at
    )


@router.get("/api/reports/{report_id}/records", response_model=ReportRecordsResponse)
async def get_report_records(
    report_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Records per page"),
    db: Session = Depends(get_db)
):
    """
    Get all records for a specific report with pagination
    """
    # Verify report exists
    report = db.query(DmarcReport).filter(DmarcReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Query records with pagination
    query = db.query(DmarcRecord).filter(DmarcRecord.report_id == report_id)
    total = query.count()

    # Order by count DESC (most impactful first), then source_ip
    offset = (page - 1) * page_size
    records = query.order_by(
        DmarcRecord.count.desc(),
        DmarcRecord.source_ip
    ).offset(offset).limit(page_size).all()

    # Convert to response models
    records_data = [RecordDetailResponse.from_orm(record) for record in records]

    return ReportRecordsResponse(
        report_id=report_id,
        total=total,
        page=page,
        page_size=page_size,
        records=records_data
    )


@router.get("/api/rollup/summary", response_model=SummaryStats)
async def rollup_summary(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    start: Optional[datetime] = Query(None, description="Filter by start date"),
    end: Optional[datetime] = Query(None, description="Filter by end date"),
    source_ip: Optional[str] = Query(None, description="Filter by source IP"),
    source_ip_range: Optional[str] = Query(None, description="Filter by IP range (CIDR)"),
    dkim_result: Optional[str] = Query(None, description="Filter by DKIM result"),
    spf_result: Optional[str] = Query(None, description="Filter by SPF result"),
    disposition: Optional[str] = Query(None, description="Filter by disposition"),
    org_name: Optional[str] = Query(None, description="Filter by organization name"),
    db: Session = Depends(get_db)
):
    """
    Get summary statistics with pass/fail counts and disposition breakdown
    """
    # Build query for reports
    reports_query = db.query(DmarcReport)

    if domain:
        reports_query = reports_query.filter(DmarcReport.domain == domain)
    if start:
        reports_query = reports_query.filter(DmarcReport.date_begin >= start)
    if end:
        reports_query = reports_query.filter(DmarcReport.date_end <= end)
    if org_name:
        reports_query = reports_query.filter(DmarcReport.org_name.ilike(f"%{org_name}%"))

    # Get report IDs and date range
    reports = reports_query.all()
    total_reports = len(reports)

    if total_reports == 0:
        return SummaryStats(
            total_messages=0,
            total_reports=0,
            pass_count=0,
            fail_count=0,
            pass_percentage=0.0,
            fail_percentage=0.0,
            disposition_none=0,
            disposition_quarantine=0,
            disposition_reject=0,
            date_range_start=None,
            date_range_end=None
        )

    report_ids = [r.id for r in reports]
    date_range_start = min(r.date_begin for r in reports)
    date_range_end = max(r.date_end for r in reports)

    # Query records with aggregations
    records_query = db.query(
        func.sum(DmarcRecord.count).label('total_count'),
        func.sum(
            case(
                (and_(DmarcRecord.dkim_result == 'pass', DmarcRecord.spf_result == 'pass'), DmarcRecord.count),
                else_=0
            )
        ).label('pass_count'),
        func.sum(
            case(
                (DmarcRecord.disposition == 'none', DmarcRecord.count),
                else_=0
            )
        ).label('disp_none'),
        func.sum(
            case(
                (DmarcRecord.disposition == 'quarantine', DmarcRecord.count),
                else_=0
            )
        ).label('disp_quarantine'),
        func.sum(
            case(
                (DmarcRecord.disposition == 'reject', DmarcRecord.count),
                else_=0
            )
        ).label('disp_reject')
    ).filter(DmarcRecord.report_id.in_(report_ids))

    # Apply record-level filters
    if source_ip:
        records_query = records_query.filter(DmarcRecord.source_ip == source_ip)
    if source_ip_range:
        from app.utils.ip_utils import ip_in_range
        # For CIDR filtering, filter in memory for now
        # TODO: Could use PostgreSQL inet operators for better performance
        all_records = db.query(DmarcRecord).filter(DmarcRecord.report_id.in_(report_ids)).all()
        filtered_ids = [r.id for r in all_records if ip_in_range(r.source_ip, source_ip_range)]
        if filtered_ids:
            records_query = records_query.filter(DmarcRecord.id.in_(filtered_ids))
        else:
            # No matching IPs, return empty stats
            return SummaryStats(
                total_messages=0,
                total_reports=0,
                pass_count=0,
                fail_count=0,
                pass_percentage=0.0,
                fail_percentage=0.0,
                disposition_none=0,
                disposition_quarantine=0,
                disposition_reject=0,
                date_range_start=date_range_start,
                date_range_end=date_range_end
            )
    if dkim_result:
        records_query = records_query.filter(DmarcRecord.dkim_result == dkim_result)
    if spf_result:
        records_query = records_query.filter(DmarcRecord.spf_result == spf_result)
    if disposition:
        records_query = records_query.filter(DmarcRecord.disposition == disposition)

    records_query = records_query.one()

    total_messages = records_query.total_count or 0
    pass_count = records_query.pass_count or 0
    fail_count = total_messages - pass_count

    pass_percentage = (pass_count / total_messages * 100) if total_messages > 0 else 0.0
    fail_percentage = (fail_count / total_messages * 100) if total_messages > 0 else 0.0

    return SummaryStats(
        total_messages=total_messages,
        total_reports=total_reports,
        pass_count=pass_count,
        fail_count=fail_count,
        pass_percentage=round(pass_percentage, 2),
        fail_percentage=round(fail_percentage, 2),
        disposition_none=records_query.disp_none or 0,
        disposition_quarantine=records_query.disp_quarantine or 0,
        disposition_reject=records_query.disp_reject or 0,
        date_range_start=date_range_start,
        date_range_end=date_range_end
    )


@router.get("/api/rollup/sources", response_model=SourceIPListResponse)
async def rollup_sources(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    start: Optional[datetime] = Query(None, description="Filter by start date"),
    end: Optional[datetime] = Query(None, description="Filter by end date"),
    dkim_result: Optional[str] = Query(None, description="Filter by DKIM result"),
    spf_result: Optional[str] = Query(None, description="Filter by SPF result"),
    disposition: Optional[str] = Query(None, description="Filter by disposition"),
    org_name: Optional[str] = Query(None, description="Filter by organization"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db)
):
    """
    Get statistics grouped by source IP with pass/fail counts
    """
    # Build query for reports
    reports_query = db.query(DmarcReport.id)

    if domain:
        reports_query = reports_query.filter(DmarcReport.domain == domain)
    if start:
        reports_query = reports_query.filter(DmarcReport.date_begin >= start)
    if end:
        reports_query = reports_query.filter(DmarcReport.date_end <= end)
    if org_name:
        reports_query = reports_query.join(DmarcReport).filter(DmarcReport.org_name.ilike(f"%{org_name}%"))

    report_ids = [r.id for r in reports_query.all()]

    if not report_ids:
        return SourceIPListResponse(
            sources=[],
            total=0,
            page=page,
            page_size=page_size
        )

    # Query records grouped by source IP
    sources_query = db.query(
        DmarcRecord.source_ip,
        func.sum(DmarcRecord.count).label('total_count'),
        func.sum(
            case(
                (and_(DmarcRecord.dkim_result == 'pass', DmarcRecord.spf_result == 'pass'), DmarcRecord.count),
                else_=0
            )
        ).label('pass_count'),
        func.count(DmarcRecord.id).label('report_count')
    ).filter(
        DmarcRecord.report_id.in_(report_ids)
    )

    # Apply record-level filters
    if dkim_result:
        sources_query = sources_query.filter(DmarcRecord.dkim_result == dkim_result)
    if spf_result:
        sources_query = sources_query.filter(DmarcRecord.spf_result == spf_result)
    if disposition:
        sources_query = sources_query.filter(DmarcRecord.disposition == disposition)

    sources_query = sources_query.group_by(
        DmarcRecord.source_ip
    ).order_by(
        func.sum(DmarcRecord.count).desc()
    )

    # Get total count
    total = sources_query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    sources = sources_query.offset(offset).limit(page_size).all()

    # Build response
    sources_data = []
    for src in sources:
        total_count = src.total_count or 0
        pass_count = src.pass_count or 0
        fail_count = total_count - pass_count
        pass_percentage = (pass_count / total_count * 100) if total_count > 0 else 0.0

        sources_data.append(SourceIPStats(
            source_ip=src.source_ip,
            total_count=total_count,
            pass_count=pass_count,
            fail_count=fail_count,
            pass_percentage=round(pass_percentage, 2),
            report_count=src.report_count
        ))

    return SourceIPListResponse(
        sources=sources_data,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/api/rollup/alignment", response_model=AlignmentStats)
async def rollup_alignment(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    start: Optional[datetime] = Query(None, description="Filter by start date"),
    end: Optional[datetime] = Query(None, description="Filter by end date"),
    db: Session = Depends(get_db)
):
    """
    Get SPF and DKIM alignment statistics
    """
    # Build query for reports
    reports_query = db.query(DmarcReport.id)

    if domain:
        reports_query = reports_query.filter(DmarcReport.domain == domain)
    if start:
        reports_query = reports_query.filter(DmarcReport.date_begin >= start)
    if end:
        reports_query = reports_query.filter(DmarcReport.date_end <= end)

    report_ids = [r.id for r in reports_query.all()]

    if not report_ids:
        return AlignmentStats(
            total_messages=0,
            spf_pass=0,
            spf_fail=0,
            spf_other=0,
            spf_pass_percentage=0.0,
            dkim_pass=0,
            dkim_fail=0,
            dkim_other=0,
            dkim_pass_percentage=0.0,
            both_pass=0,
            both_pass_percentage=0.0,
            either_pass=0,
            either_pass_percentage=0.0
        )

    # Query records with alignment aggregations
    stats = db.query(
        func.sum(DmarcRecord.count).label('total_count'),
        func.sum(
            case((DmarcRecord.spf_result == 'pass', DmarcRecord.count), else_=0)
        ).label('spf_pass'),
        func.sum(
            case((DmarcRecord.spf_result == 'fail', DmarcRecord.count), else_=0)
        ).label('spf_fail'),
        func.sum(
            case((DmarcRecord.dkim_result == 'pass', DmarcRecord.count), else_=0)
        ).label('dkim_pass'),
        func.sum(
            case((DmarcRecord.dkim_result == 'fail', DmarcRecord.count), else_=0)
        ).label('dkim_fail'),
        func.sum(
            case(
                (and_(DmarcRecord.dkim_result == 'pass', DmarcRecord.spf_result == 'pass'), DmarcRecord.count),
                else_=0
            )
        ).label('both_pass'),
        func.sum(
            case(
                (or_(DmarcRecord.dkim_result == 'pass', DmarcRecord.spf_result == 'pass'), DmarcRecord.count),
                else_=0
            )
        ).label('either_pass')
    ).filter(DmarcRecord.report_id.in_(report_ids)).one()

    total_messages = stats.total_count or 0
    spf_pass = stats.spf_pass or 0
    spf_fail = stats.spf_fail or 0
    dkim_pass = stats.dkim_pass or 0
    dkim_fail = stats.dkim_fail or 0
    both_pass = stats.both_pass or 0
    either_pass = stats.either_pass or 0

    spf_other = total_messages - spf_pass - spf_fail
    dkim_other = total_messages - dkim_pass - dkim_fail

    spf_pass_percentage = (spf_pass / total_messages * 100) if total_messages > 0 else 0.0
    dkim_pass_percentage = (dkim_pass / total_messages * 100) if total_messages > 0 else 0.0
    both_pass_percentage = (both_pass / total_messages * 100) if total_messages > 0 else 0.0
    either_pass_percentage = (either_pass / total_messages * 100) if total_messages > 0 else 0.0

    return AlignmentStats(
        total_messages=total_messages,
        spf_pass=spf_pass,
        spf_fail=spf_fail,
        spf_other=spf_other,
        spf_pass_percentage=round(spf_pass_percentage, 2),
        dkim_pass=dkim_pass,
        dkim_fail=dkim_fail,
        dkim_other=dkim_other,
        dkim_pass_percentage=round(dkim_pass_percentage, 2),
        both_pass=both_pass,
        both_pass_percentage=round(both_pass_percentage, 2),
        either_pass=either_pass,
        either_pass_percentage=round(either_pass_percentage, 2)
    )


@router.get("/api/rollup/timeline", response_model=TimelineListResponse)
async def rollup_timeline(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    start: Optional[datetime] = Query(None, description="Filter by start date"),
    end: Optional[datetime] = Query(None, description="Filter by end date"),
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    db: Session = Depends(get_db)
):
    """
    Get timeline statistics grouped by date (optimized with caching)
    """
    from datetime import timedelta
    from sqlalchemy import cast, Date, func, case, and_
    from app.services.cache import get_cache, cache_key

    # Try cache first
    cache = get_cache()
    cache_k = cache_key("timeline", domain=domain, days=days, start=start, end=end)
    cached_result = cache.get(cache_k)
    if cached_result:
        return TimelineListResponse(**cached_result)

    # Build optimized query with JOIN and aggregation
    query = db.query(
        cast(DmarcReport.date_end, Date).label('date'),
        func.count(DmarcReport.id).label('report_count'),
        func.sum(DmarcRecord.count).label('total_messages'),
        func.sum(
            case(
                (and_(DmarcRecord.dkim_result == 'pass',
                      DmarcRecord.spf_result == 'pass'),
                 DmarcRecord.count),
                else_=0
            )
        ).label('pass_count')
    ).join(
        DmarcRecord, DmarcReport.id == DmarcRecord.report_id
    )

    # Apply filters
    if domain:
        query = query.filter(DmarcReport.domain == domain)

    if start and end:
        query = query.filter(
            DmarcReport.date_begin >= start,
            DmarcReport.date_end <= end
        )
    elif not start and not end:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        query = query.filter(
            DmarcReport.date_end >= start_date,
            DmarcReport.date_end <= end_date
        )

    # Group by date and order
    query = query.group_by(cast(DmarcReport.date_end, Date))
    query = query.order_by(cast(DmarcReport.date_end, Date))

    # Execute single query
    results = query.all()

    # Format response
    timeline = []
    for row in results:
        total = row.total_messages or 0
        passed = row.pass_count or 0
        failed = total - passed

        timeline.append(TimelineStats(
            date=row.date.strftime('%Y-%m-%d'),
            total_messages=total,
            pass_count=passed,
            fail_count=failed,
            report_count=row.report_count
        ))

    response_data = {
        "timeline": [t.dict() for t in timeline],
        "total": len(timeline)
    }

    # Cache for 5 minutes
    cache.set(cache_k, response_data, ttl=300)

    return TimelineListResponse(**response_data)


@router.get("/api/rollup/alignment-breakdown")
async def rollup_alignment_breakdown(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    start: Optional[datetime] = Query(None, description="Filter by start date"),
    end: Optional[datetime] = Query(None, description="Filter by end date"),
    days: int = Query(30, ge=1, le=365, description="Number of days"),
    db: Session = Depends(get_db)
):
    """
    Get detailed alignment breakdown for stacked bar chart
    Returns counts for: both_pass, dkim_only, spf_only, both_fail
    """
    from datetime import timedelta
    from app.services.cache import get_cache, cache_key

    # Try cache first
    cache = get_cache()
    cache_k = cache_key("alignment_breakdown", domain=domain, days=days, start=start, end=end)
    cached = cache.get(cache_k)
    if cached:
        return cached

    # Build query for report IDs
    reports_query = db.query(DmarcReport.id)

    if domain:
        reports_query = reports_query.filter(DmarcReport.domain == domain)

    # Date filtering
    if start and end:
        reports_query = reports_query.filter(
            DmarcReport.date_begin >= start,
            DmarcReport.date_end <= end
        )
    elif not start and not end:
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=days)
        reports_query = reports_query.filter(
            DmarcReport.date_end >= start_dt,
            DmarcReport.date_end <= end_dt
        )

    report_ids = [r.id for r in reports_query.all()]

    if not report_ids:
        result = {
            "both_pass": 0,
            "dkim_only": 0,
            "spf_only": 0,
            "both_fail": 0,
            "total": 0
        }
        cache.set(cache_k, result, ttl=300)
        return result

    # Aggregate by alignment status
    stats = db.query(
        func.sum(
            case(
                (and_(DmarcRecord.dkim_result == 'pass', DmarcRecord.spf_result == 'pass'),
                 DmarcRecord.count),
                else_=0
            )
        ).label('both_pass'),
        func.sum(
            case(
                (and_(DmarcRecord.dkim_result == 'pass', DmarcRecord.spf_result != 'pass'),
                 DmarcRecord.count),
                else_=0
            )
        ).label('dkim_only'),
        func.sum(
            case(
                (and_(DmarcRecord.dkim_result != 'pass', DmarcRecord.spf_result == 'pass'),
                 DmarcRecord.count),
                else_=0
            )
        ).label('spf_only'),
        func.sum(
            case(
                (and_(DmarcRecord.dkim_result != 'pass', DmarcRecord.spf_result != 'pass'),
                 DmarcRecord.count),
                else_=0
            )
        ).label('both_fail'),
        func.sum(DmarcRecord.count).label('total')
    ).filter(DmarcRecord.report_id.in_(report_ids)).one()

    result = {
        "both_pass": stats.both_pass or 0,
        "dkim_only": stats.dkim_only or 0,
        "spf_only": stats.spf_only or 0,
        "both_fail": stats.both_fail or 0,
        "total": stats.total or 0
    }

    # Cache for 5 minutes
    cache.set(cache_k, result, ttl=300)

    return result


@router.get("/api/rollup/failure-trend")
async def rollup_failure_trend(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    days: int = Query(30, ge=1, le=365, description="Number of days"),
    window_size: int = Query(7, ge=1, le=30, description="Moving average window"),
    db: Session = Depends(get_db)
):
    """
    Get failure rate trend over time with moving average
    """
    from datetime import timedelta
    from sqlalchemy import cast, Date
    from app.services.cache import get_cache, cache_key

    cache = get_cache()
    cache_k = cache_key("failure_trend", domain=domain, days=days, window=window_size)
    cached = cache.get(cache_k)
    if cached:
        return cached

    # Get daily failure rates
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    query = db.query(
        cast(DmarcReport.date_end, Date).label('date'),
        func.sum(DmarcRecord.count).label('total'),
        func.sum(
            case(
                (and_(DmarcRecord.dkim_result != 'pass', DmarcRecord.spf_result != 'pass'),
                 DmarcRecord.count),
                else_=0
            )
        ).label('failures')
    ).join(
        DmarcRecord, DmarcReport.id == DmarcRecord.report_id
    ).filter(
        DmarcReport.date_end >= start_date,
        DmarcReport.date_end <= end_date
    )

    if domain:
        query = query.filter(DmarcReport.domain == domain)

    query = query.group_by(cast(DmarcReport.date_end, Date))
    query = query.order_by(cast(DmarcReport.date_end, Date))

    results = query.all()

    # Calculate failure rates and moving average
    trend_data = []
    failure_rates = []

    for row in results:
        total = row.total or 0
        failures = row.failures or 0
        failure_rate = (failures / total * 100) if total > 0 else 0

        failure_rates.append(failure_rate)

        # Calculate moving average
        if len(failure_rates) >= window_size:
            moving_avg = sum(failure_rates[-window_size:]) / window_size
        else:
            moving_avg = sum(failure_rates) / len(failure_rates) if failure_rates else 0

        trend_data.append({
            "date": row.date.strftime('%Y-%m-%d'),
            "failure_rate": round(failure_rate, 2),
            "moving_average": round(moving_avg, 2),
            "total_messages": total,
            "failed_messages": failures
        })

    result = {
        "trend": trend_data,
        "window_size": window_size
    }

    cache.set(cache_k, result, ttl=300)
    return result


@router.get("/api/rollup/top-organizations")
async def rollup_top_organizations(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    days: int = Query(30, ge=1, le=365, description="Number of days"),
    limit: int = Query(10, ge=1, le=50, description="Number of organizations"),
    db: Session = Depends(get_db)
):
    """
    Get top sending organizations by message volume
    """
    from datetime import timedelta
    from app.services.cache import get_cache, cache_key

    cache = get_cache()
    cache_k = cache_key("top_orgs", domain=domain, days=days, limit=limit)
    cached = cache.get(cache_k)
    if cached:
        return cached

    # Date filtering
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Aggregate by organization
    query = db.query(
        DmarcReport.org_name,
        func.count(DmarcReport.id).label('report_count'),
        func.sum(DmarcRecord.count).label('total_messages'),
        func.sum(
            case(
                (and_(DmarcRecord.dkim_result == 'pass', DmarcRecord.spf_result == 'pass'),
                 DmarcRecord.count),
                else_=0
            )
        ).label('pass_count')
    ).join(
        DmarcRecord, DmarcReport.id == DmarcRecord.report_id
    ).filter(
        DmarcReport.date_end >= start_date,
        DmarcReport.date_end <= end_date
    )

    if domain:
        query = query.filter(DmarcReport.domain == domain)

    query = query.group_by(DmarcReport.org_name)
    query = query.order_by(func.sum(DmarcRecord.count).desc())
    query = query.limit(limit)

    results = query.all()

    organizations = []
    for row in results:
        total = row.total_messages or 0
        passed = row.pass_count or 0
        failed = total - passed
        pass_rate = (passed / total * 100) if total > 0 else 0

        organizations.append({
            "org_name": row.org_name,
            "report_count": row.report_count,
            "total_messages": total,
            "pass_count": passed,
            "fail_count": failed,
            "pass_percentage": round(pass_rate, 2)
        })

    result = {
        "organizations": organizations,
        "total": len(organizations)
    }

    cache.set(cache_k, result, ttl=300)
    return result


@router.post("/api/ingest/trigger", response_model=IngestTriggerResponse)
@limiter.limit("10/minute")
async def trigger_ingest(
    request: Request,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Manually trigger email ingestion

    Requires API key authentication (X-API-Key header)
    Rate limit: 10 requests per minute

    Checks configured email inbox for DMARC reports and ingests them.
    Requires email settings to be configured in environment variables.
    """
    from app.services.ingestion import IngestionService
    from app.config import get_settings

    settings = get_settings()

    # Check if email is configured
    if not all([settings.email_host, settings.email_user, settings.email_password]):
        return IngestTriggerResponse(
            message="Email not configured. Set EMAIL_HOST, EMAIL_USER, and EMAIL_PASSWORD in environment.",
            reports_ingested=0,
            emails_checked=0
        )

    try:
        service = IngestionService(db)
        stats = service.ingest_from_inbox(limit=50)

        return IngestTriggerResponse(
            message=f"Ingestion complete: {stats['attachments_ingested']} new reports from {stats['emails_checked']} emails ({stats['duplicates_skipped']} duplicates skipped)",
            reports_ingested=stats['attachments_ingested'],
            emails_checked=stats['emails_checked']
        )
    except Exception as e:
        logger.error(f"Error during manual ingestion: {str(e)}", exc_info=True)
        return IngestTriggerResponse(
            message=f"Error during ingestion: {str(e)}",
            reports_ingested=0,
            emails_checked=0
        )


@router.post("/api/process/trigger", response_model=ProcessTriggerResponse)
@limiter.limit("10/minute")
async def trigger_process(
    request: Request,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Manually trigger processing of pending DMARC reports

    Requires API key authentication (X-API-Key header)
    Rate limit: 10 requests per minute
    """
    from app.services.processing import ReportProcessor
    from app.config import get_settings

    settings = get_settings()
    processor = ReportProcessor(db, settings.raw_reports_path)

    try:
        processed, failed = processor.process_pending_reports(limit=1000)

        return ProcessTriggerResponse(
            message=f"Processing complete: {processed} reports processed successfully, {failed} failed",
            reports_processed=processed,
            reports_failed=failed
        )
    except Exception as e:
        return ProcessTriggerResponse(
            message=f"Error during processing: {str(e)}",
            reports_processed=0,
            reports_failed=0
        )


@router.post("/api/upload", response_model=UploadReportsResponse)
@limiter.limit("20/hour")
async def upload_reports(
    request: Request,
    files: List[UploadFile] = File(..., description="DMARC report files (.xml, .gz, .zip)"),
    auto_process: bool = Query(True, description="Automatically process uploaded files"),
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Bulk upload DMARC report files for analysis

    Requires API key authentication (X-API-Key header)
    Rate limit: 20 uploads per hour

    Supports:
    - Multiple file upload (multipart/form-data)
    - Automatic deduplication via SHA256 hashing
    - Optional auto-processing after upload
    - File type validation (.xml, .gz, .zip only)
    - File size limits (50MB per file)

    Returns detailed upload statistics and per-file status
    """
    from app.services.ingestion import IngestionService
    from app.services.processing import ReportProcessor
    from app.config import get_settings

    settings = get_settings()
    ingestion_service = IngestionService(db, settings.raw_reports_path)

    # Constants
    MAX_FILE_SIZE = 52_428_800  # 50MB
    ALLOWED_EXTENSIONS = ['.xml', '.gz', '.zip']

    # Track results
    uploaded_files: List[UploadedFileDetail] = []
    total_files = len(files)
    uploaded_count = 0
    duplicate_count = 0
    error_count = 0
    invalid_count = 0

    # Process each file
    for upload_file in files:
        filename = upload_file.filename
        file_size = 0

        try:
            # Read file content
            content = await upload_file.read()
            file_size = len(content)

            # Validate file extension
            ext = filename[filename.rfind('.'):].lower() if '.' in filename else ''
            if ext not in ALLOWED_EXTENSIONS:
                uploaded_files.append(UploadedFileDetail(
                    filename=filename,
                    status="invalid",
                    file_size=file_size,
                    error_message=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
                ))
                invalid_count += 1
                continue

            # Validate file size
            if file_size > MAX_FILE_SIZE:
                uploaded_files.append(UploadedFileDetail(
                    filename=filename,
                    status="invalid",
                    file_size=file_size,
                    error_message=f"File too large. Maximum size: {MAX_FILE_SIZE // 1_048_576}MB"
                ))
                invalid_count += 1
                continue

            # Generate synthetic metadata for upload
            timestamp = datetime.utcnow()
            content_hash = ingestion_service.storage.compute_hash(content)
            message_id = f"upload-{timestamp.strftime('%Y%m%d%H%M%S')}-{content_hash[:8]}"

            # Process through ingestion service
            success, ingested_record = ingestion_service.process_attachment(
                filename=filename,
                content=content,
                message_id=message_id,
                received_at=timestamp
            )

            if success and ingested_record:
                uploaded_files.append(UploadedFileDetail(
                    filename=filename,
                    status="uploaded",
                    file_size=file_size,
                    content_hash=content_hash,
                    ingestion_record_id=ingested_record.id
                ))
                uploaded_count += 1
            else:
                # Duplicate file
                uploaded_files.append(UploadedFileDetail(
                    filename=filename,
                    status="duplicate",
                    file_size=file_size,
                    content_hash=content_hash,
                    error_message="File already exists in system"
                ))
                duplicate_count += 1

        except Exception as e:
            logger.error(f"Error processing upload file {filename}: {str(e)}")
            uploaded_files.append(UploadedFileDetail(
                filename=filename,
                status="error",
                file_size=file_size,
                error_message=str(e)
            ))
            error_count += 1

    # Auto-process if requested
    reports_processed = None
    reports_failed = None

    if auto_process and uploaded_count > 0:
        try:
            processor = ReportProcessor(db, settings.raw_reports_path)
            reports_processed, reports_failed = processor.process_pending_reports(limit=1000)
            logger.info(f"Auto-processed {reports_processed} reports ({reports_failed} failed)")
        except Exception as e:
            logger.error(f"Error during auto-processing: {str(e)}")
            reports_processed = 0
            reports_failed = 0

    # Build response message
    message_parts = []
    if uploaded_count > 0:
        message_parts.append(f"{uploaded_count} uploaded")
    if duplicate_count > 0:
        message_parts.append(f"{duplicate_count} duplicates")
    if error_count > 0:
        message_parts.append(f"{error_count} errors")
    if invalid_count > 0:
        message_parts.append(f"{invalid_count} invalid")

    message = f"Upload complete: {', '.join(message_parts)}" if message_parts else "No files uploaded"

    return UploadReportsResponse(
        message=message,
        total_files=total_files,
        uploaded=uploaded_count,
        duplicates=duplicate_count,
        errors=error_count,
        invalid_files=invalid_count,
        files=uploaded_files,
        auto_processed=auto_process and uploaded_count > 0,
        reports_processed=reports_processed,
        reports_failed=reports_failed
    )


@router.post("/api/alerts/check", response_model=CheckAlertsResponse)
async def check_alerts(
    domain: Optional[str] = Query(None, description="Check alerts for specific domain"),
    send_notifications: bool = Query(True, description="Send notifications if alerts found"),
    db: Session = Depends(get_db)
):
    """
    Manually check alert conditions and optionally send notifications

    This endpoint allows you to:
    - Check current alert conditions without waiting for scheduler
    - Test alert configuration
    - Optionally send notifications immediately
    """
    from app.services.alerting import AlertService
    from app.services.notifications import NotificationService
    from app.config import get_settings

    settings = get_settings()

    if not settings.enable_alerts:
        return CheckAlertsResponse(
            alerts_found=0,
            alerts=[],
            notifications_sent=0,
            notification_channels={'error': 'Alerting is not enabled. Set ENABLE_ALERTS=true'}
        )

    try:
        # Check alerts
        alert_service = AlertService(db)
        alerts = alert_service.check_all_alerts(domain=domain)

        response_alerts = [
            AlertDetail(
                alert_type=alert.alert_type,
                severity=alert.severity,
                title=alert.title,
                message=alert.message,
                details=alert.details,
                timestamp=alert.timestamp
            )
            for alert in alerts
        ]

        # Send notifications if requested
        notifications_sent = 0
        notification_channels = {}

        if alerts and send_notifications:
            notification_service = NotificationService()
            stats = notification_service.send_alerts(alerts)
            notifications_sent = stats['sent']
            notification_channels = stats['channels']

        return CheckAlertsResponse(
            alerts_found=len(alerts),
            alerts=response_alerts,
            notifications_sent=notifications_sent,
            notification_channels=notification_channels
        )

    except Exception as e:
        logger.error(f"Error checking alerts: {str(e)}", exc_info=True)
        return CheckAlertsResponse(
            alerts_found=0,
            alerts=[],
            notifications_sent=0,
            notification_channels={'error': str(e)}
        )


@router.get("/api/alerts/config", response_model=AlertConfigResponse)
async def get_alert_config():
    """
    Get current alert configuration and status

    Shows:
    - Whether alerting is enabled
    - Current thresholds
    - Configured notification channels
    """
    from app.config import get_settings

    settings = get_settings()

    # Check notification channels
    email_configured = bool(
        settings.smtp_host and
        settings.smtp_from and
        settings.alert_email_to
    )

    slack_configured = bool(settings.slack_webhook_url)
    discord_configured = bool(settings.discord_webhook_url)
    teams_configured = bool(settings.teams_webhook_url)
    webhook_configured = bool(settings.webhook_url)

    return AlertConfigResponse(
        enabled=settings.enable_alerts,
        failure_warning_threshold=settings.alert_failure_warning,
        failure_critical_threshold=settings.alert_failure_critical,
        volume_spike_threshold=settings.alert_volume_spike,
        volume_drop_threshold=settings.alert_volume_drop,
        email_configured=email_configured,
        slack_configured=slack_configured,
        discord_configured=discord_configured,
        teams_configured=teams_configured,
        webhook_configured=webhook_configured
    )


# ============================================================================
# EXPORT ENDPOINTS
# ============================================================================

@router.get("/api/export/reports/csv")
@limiter.limit("10/minute")
async def export_reports_csv(
    request: Request,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key),
    domain: Optional[str] = Query(None),
    days: Optional[int] = Query(30),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    org_name: Optional[str] = Query(None)
):
    """
    Export DMARC reports to CSV

    Requires API key authentication. Rate limited to 10 requests per minute.

    Returns CSV file with report metadata including:
    - Report ID, organization, domain
    - Date range, policy settings
    - Record count and message totals
    """
    from app.services.export_csv import CSVExportService

    # Parse dates if provided
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    # Generate CSV
    export_service = CSVExportService(db)
    csv_content = export_service.export_reports(
        domain=domain,
        days=days,
        start_date=start_dt,
        end_date=end_dt,
        org_name=org_name
    )

    # Create filename with timestamp
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f"dmarc_reports_{timestamp}.csv"

    # Return as downloadable file
    return StreamingResponse(
        io.BytesIO(csv_content.encode('utf-8')),
        media_type='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'X-Content-Type-Options': 'nosniff'
        }
    )


@router.get("/api/export/records/csv")
@limiter.limit("10/minute")
async def export_records_csv(
    request: Request,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key),
    domain: Optional[str] = Query(None),
    days: Optional[int] = Query(30),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    source_ip: Optional[str] = Query(None),
    dkim_result: Optional[str] = Query(None),
    spf_result: Optional[str] = Query(None),
    disposition: Optional[str] = Query(None),
    org_name: Optional[str] = Query(None),
    limit: int = Query(10000, le=10000)
):
    """
    Export DMARC records to CSV with full details

    Requires API key authentication. Rate limited to 10 requests per minute.
    Maximum 10,000 records per export.

    Returns CSV file with detailed record information including:
    - Source IPs, message counts, dispositions
    - DKIM and SPF authentication results
    - Header and envelope information
    """
    from app.services.export_csv import CSVExportService

    # Parse dates if provided
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    # Generate CSV
    export_service = CSVExportService(db)
    csv_content = export_service.export_records(
        domain=domain,
        days=days,
        start_date=start_dt,
        end_date=end_dt,
        source_ip=source_ip,
        dkim_result=dkim_result,
        spf_result=spf_result,
        disposition=disposition,
        org_name=org_name,
        limit=limit
    )

    # Create filename with timestamp
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f"dmarc_records_{timestamp}.csv"

    # Return as downloadable file
    return StreamingResponse(
        io.BytesIO(csv_content.encode('utf-8')),
        media_type='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'X-Content-Type-Options': 'nosniff'
        }
    )


@router.get("/api/export/sources/csv")
@limiter.limit("10/minute")
async def export_sources_csv(
    request: Request,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key),
    domain: Optional[str] = Query(None),
    days: Optional[int] = Query(30),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    org_name: Optional[str] = Query(None),
    limit: int = Query(1000, le=1000)
):
    """
    Export aggregated source IP statistics to CSV

    Requires API key authentication. Rate limited to 10 requests per minute.
    Maximum 1,000 sources per export.

    Returns CSV file with source IP aggregations including:
    - Total message counts
    - Pass/fail statistics
    - Pass percentages
    """
    from app.services.export_csv import CSVExportService

    # Parse dates if provided
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    # Generate CSV
    export_service = CSVExportService(db)
    csv_content = export_service.export_sources(
        domain=domain,
        days=days,
        start_date=start_dt,
        end_date=end_dt,
        org_name=org_name,
        limit=limit
    )

    # Create filename with timestamp
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f"dmarc_sources_{timestamp}.csv"

    # Return as downloadable file
    return StreamingResponse(
        io.BytesIO(csv_content.encode('utf-8')),
        media_type='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'X-Content-Type-Options': 'nosniff'
        }
    )


@router.get("/api/export/report/pdf")
@limiter.limit("5/minute")
async def export_summary_pdf(
    request: Request,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key),
    domain: Optional[str] = Query(None),
    days: Optional[int] = Query(30),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """
    Export comprehensive DMARC summary report as PDF

    Requires API key authentication. Rate limited to 5 requests per minute
    (more expensive than CSV exports).

    Returns PDF document with:
    - Executive summary with statistics
    - Compliance pie chart
    - Authentication alignment breakdown
    - Top source IPs table
    """
    from app.services.export_pdf import PDFExportService

    # Parse dates if provided
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    # Generate PDF
    export_service = PDFExportService(db)
    pdf_bytes = export_service.generate_summary_report(
        domain=domain,
        days=days,
        start_date=start_dt,
        end_date=end_dt
    )

    # Create filename with timestamp
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f"dmarc_summary_{timestamp}.pdf"

    # Return as downloadable file
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'X-Content-Type-Options': 'nosniff'
        }
    )
