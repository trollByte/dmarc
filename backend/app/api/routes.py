"""
API routes for DMARC reporting and rollups
"""
from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case
from typing import Optional, List
from datetime import datetime
import logging

from app.database import get_db
from app.models import DmarcReport, DmarcRecord
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
    UploadedFileDetail
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


@router.get("/api/rollup/summary", response_model=SummaryStats)
async def rollup_summary(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    start: Optional[datetime] = Query(None, description="Filter by start date"),
    end: Optional[datetime] = Query(None, description="Filter by end date"),
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
    ).filter(DmarcRecord.report_id.in_(report_ids)).one()

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
    ).group_by(
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
    Get timeline statistics grouped by date
    """
    from datetime import timedelta
    from sqlalchemy import cast, Date

    # Build query for reports
    reports_query = db.query(DmarcReport)

    if domain:
        reports_query = reports_query.filter(DmarcReport.domain == domain)
    if start:
        reports_query = reports_query.filter(DmarcReport.date_begin >= start)
    if end:
        reports_query = reports_query.filter(DmarcReport.date_end <= end)

    # If no date range specified, use last N days
    if not start and not end:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        reports_query = reports_query.filter(
            DmarcReport.date_end >= start_date,
            DmarcReport.date_end <= end_date
        )

    # Get all matching reports with their records
    reports = reports_query.all()

    # Group by date
    timeline_data = {}

    for report in reports:
        # Use date_end as the key date
        date_key = report.date_end.strftime('%Y-%m-%d')

        if date_key not in timeline_data:
            timeline_data[date_key] = {
                'total_messages': 0,
                'pass_count': 0,
                'fail_count': 0,
                'report_count': 0
            }

        timeline_data[date_key]['report_count'] += 1

        # Aggregate record counts
        for record in report.records:
            timeline_data[date_key]['total_messages'] += record.count

            # Check if both DKIM and SPF passed
            if record.dkim_result == 'pass' and record.spf_result == 'pass':
                timeline_data[date_key]['pass_count'] += record.count
            else:
                timeline_data[date_key]['fail_count'] += record.count

    # Convert to list and sort by date
    timeline = []
    for date, stats in sorted(timeline_data.items()):
        timeline.append(TimelineStats(
            date=date,
            total_messages=stats['total_messages'],
            pass_count=stats['pass_count'],
            fail_count=stats['fail_count'],
            report_count=stats['report_count']
        ))

    return TimelineListResponse(
        timeline=timeline,
        total=len(timeline)
    )


@router.post("/api/ingest/trigger", response_model=IngestTriggerResponse)
async def trigger_ingest(db: Session = Depends(get_db)):
    """
    Manually trigger email ingestion

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
async def trigger_process(db: Session = Depends(get_db)):
    """
    Manually trigger processing of pending DMARC reports
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
async def upload_reports(
    files: List[UploadFile] = File(..., description="DMARC report files (.xml, .gz, .zip)"),
    auto_process: bool = Query(True, description="Automatically process uploaded files"),
    db: Session = Depends(get_db)
):
    """
    Bulk upload DMARC report files for analysis

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
