from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional
from datetime import datetime, timedelta
from app.database import get_db
from app.models import Report, Record, ProcessedEmail
from app.schemas import (
    ReportResponse,
    ReportListResponse,
    StatsSummary,
    StatsByDate,
    StatsByDomain,
    StatsBySourceIP,
    IngestResponse
)
from app.ingest.processor import IngestProcessor
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/reports", response_model=ReportListResponse)
def get_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    domain: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """
    Get list of reports with pagination and filters

    Args:
        page: Page number (1-indexed)
        page_size: Number of reports per page
        domain: Filter by domain
        start_date: Filter by start date
        end_date: Filter by end date
    """
    query = db.query(Report)

    # Apply filters
    if domain:
        query = query.filter(Report.domain == domain)
    if start_date:
        query = query.filter(Report.date_begin >= start_date)
    if end_date:
        query = query.filter(Report.date_end <= end_date)

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    reports = query.order_by(Report.date_end.desc()).offset(offset).limit(page_size).all()

    # Enhance reports with computed fields
    reports_data = []
    for report in reports:
        report_dict = {
            "id": report.id,
            "report_id": report.report_id,
            "org_name": report.org_name,
            "email": report.email,
            "extra_contact_info": report.extra_contact_info,
            "date_begin": report.date_begin,
            "date_end": report.date_end,
            "domain": report.domain,
            "adkim": report.adkim,
            "aspf": report.aspf,
            "p": report.p,
            "sp": report.sp,
            "pct": report.pct,
            "created_at": report.created_at,
            "records": [],
            "total_records": len(report.records),
            "pass_count": sum(1 for r in report.records if r.dkim_result == 'pass' and r.spf_result == 'pass'),
            "fail_count": sum(1 for r in report.records if r.dkim_result != 'pass' or r.spf_result != 'pass')
        }
        reports_data.append(ReportResponse(**report_dict))

    return ReportListResponse(
        reports=reports_data,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/reports/{report_id}", response_model=ReportResponse)
def get_report(report_id: int, db: Session = Depends(get_db)):
    """
    Get detailed report by ID

    Args:
        report_id: Report database ID
    """
    report = db.query(Report).filter(Report.id == report_id).first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Build response with all records
    return ReportResponse(
        id=report.id,
        report_id=report.report_id,
        org_name=report.org_name,
        email=report.email,
        extra_contact_info=report.extra_contact_info,
        date_begin=report.date_begin,
        date_end=report.date_end,
        domain=report.domain,
        adkim=report.adkim,
        aspf=report.aspf,
        p=report.p,
        sp=report.sp,
        pct=report.pct,
        created_at=report.created_at,
        records=report.records,
        total_records=len(report.records),
        pass_count=sum(1 for r in report.records if r.dkim_result == 'pass' and r.spf_result == 'pass'),
        fail_count=sum(1 for r in report.records if r.dkim_result != 'pass' or r.spf_result != 'pass')
    )


@router.get("/stats/summary", response_model=StatsSummary)
def get_stats_summary(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """
    Get summary statistics

    Args:
        start_date: Filter by start date
        end_date: Filter by end date
    """
    query = db.query(Report)

    if start_date:
        query = query.filter(Report.date_begin >= start_date)
    if end_date:
        query = query.filter(Report.date_end <= end_date)

    total_reports = query.count()

    # Get all records for the filtered reports
    report_ids = [r.id for r in query.all()]

    if not report_ids:
        return StatsSummary(
            total_reports=0,
            total_messages=0,
            pass_rate=0.0,
            fail_rate=0.0
        )

    records = db.query(Record).filter(Record.report_id.in_(report_ids)).all()

    total_messages = sum(r.count for r in records)
    pass_count = sum(r.count for r in records if r.dkim_result == 'pass' and r.spf_result == 'pass')
    fail_count = total_messages - pass_count

    pass_rate = (pass_count / total_messages * 100) if total_messages > 0 else 0
    fail_rate = (fail_count / total_messages * 100) if total_messages > 0 else 0

    return StatsSummary(
        total_reports=total_reports,
        total_messages=total_messages,
        pass_rate=pass_rate,
        fail_rate=fail_rate
    )


@router.get("/stats/by-date", response_model=List[StatsByDate])
def get_stats_by_date(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Get statistics grouped by date

    Args:
        start_date: Filter by start date
        end_date: Filter by end date
        limit: Maximum number of days to return
    """
    # Default to last 30 days if not specified
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=limit)

    query = db.query(Report).filter(
        Report.date_end >= start_date,
        Report.date_end <= end_date
    )

    reports = query.all()

    # Group by date
    date_stats = {}

    for report in reports:
        date_key = report.date_end.strftime('%Y-%m-%d')

        if date_key not in date_stats:
            date_stats[date_key] = {
                'pass_count': 0,
                'fail_count': 0
            }

        for record in report.records:
            if record.dkim_result == 'pass' and record.spf_result == 'pass':
                date_stats[date_key]['pass_count'] += record.count
            else:
                date_stats[date_key]['fail_count'] += record.count

    # Convert to list and sort by date
    result = []
    for date, stats in sorted(date_stats.items()):
        result.append(StatsByDate(
            date=date,
            pass_count=stats['pass_count'],
            fail_count=stats['fail_count'],
            total_count=stats['pass_count'] + stats['fail_count']
        ))

    return result


@router.get("/stats/by-domain", response_model=List[StatsByDomain])
def get_stats_by_domain(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get statistics grouped by domain

    Args:
        start_date: Filter by start date
        end_date: Filter by end date
        limit: Maximum number of domains to return
    """
    query = db.query(Report)

    if start_date:
        query = query.filter(Report.date_begin >= start_date)
    if end_date:
        query = query.filter(Report.date_end <= end_date)

    reports = query.all()

    # Group by domain
    domain_stats = {}

    for report in reports:
        if report.domain not in domain_stats:
            domain_stats[report.domain] = {
                'pass_count': 0,
                'fail_count': 0
            }

        for record in report.records:
            if record.dkim_result == 'pass' and record.spf_result == 'pass':
                domain_stats[report.domain]['pass_count'] += record.count
            else:
                domain_stats[report.domain]['fail_count'] += record.count

    # Convert to list and sort by total count
    result = []
    for domain, stats in domain_stats.items():
        result.append(StatsByDomain(
            domain=domain,
            pass_count=stats['pass_count'],
            fail_count=stats['fail_count'],
            total_count=stats['pass_count'] + stats['fail_count']
        ))

    result.sort(key=lambda x: x.total_count, reverse=True)

    return result[:limit]


@router.get("/stats/by-source-ip", response_model=List[StatsBySourceIP])
def get_stats_by_source_ip(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get statistics grouped by source IP

    Args:
        start_date: Filter by start date
        end_date: Filter by end date
        limit: Maximum number of IPs to return
    """
    query = db.query(Report)

    if start_date:
        query = query.filter(Report.date_begin >= start_date)
    if end_date:
        query = query.filter(Report.date_end <= end_date)

    report_ids = [r.id for r in query.all()]

    if not report_ids:
        return []

    # Query records grouped by source IP
    results = db.query(
        Record.source_ip,
        func.sum(Record.count).label('total_count')
    ).filter(
        Record.report_id.in_(report_ids)
    ).group_by(
        Record.source_ip
    ).order_by(
        func.sum(Record.count).desc()
    ).limit(limit).all()

    return [
        StatsBySourceIP(source_ip=ip, count=count)
        for ip, count in results
    ]


@router.post("/ingest/trigger", response_model=IngestResponse)
def trigger_ingest(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Manually trigger email ingest process

    Args:
        limit: Maximum number of emails to check
    """
    try:
        processor = IngestProcessor(db)
        emails_checked, reports_processed = processor.run(limit)

        return IngestResponse(
            message=f"Ingest completed successfully",
            reports_processed=reports_processed,
            emails_checked=emails_checked
        )

    except ValueError as e:
        # Email not configured
        raise HTTPException(status_code=400, detail=str(e))
    except ConnectionError as e:
        # Email connection failed
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Ingest failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Ingest process failed")
