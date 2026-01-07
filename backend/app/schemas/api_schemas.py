"""
API schemas for DMARC reporting endpoints
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional


# Domain schemas
class DomainInfo(BaseModel):
    """Information about a domain"""
    domain: str
    report_count: int
    earliest_report: Optional[datetime]
    latest_report: Optional[datetime]

    class Config:
        from_attributes = True


class DomainsListResponse(BaseModel):
    """Response for /api/domains"""
    domains: List[DomainInfo]
    total: int


# Report schemas
class RecordSummary(BaseModel):
    """Summary of a DMARC record"""
    id: int
    source_ip: str
    count: int
    disposition: Optional[str]
    dkim: Optional[str]
    spf: Optional[str]
    dkim_result: Optional[str]
    spf_result: Optional[str]

    class Config:
        from_attributes = True


class ReportDetail(BaseModel):
    """Detailed DMARC report"""
    id: int
    report_id: str
    org_name: str
    email: Optional[str]
    domain: str
    date_begin: datetime
    date_end: datetime
    p: str
    sp: Optional[str]
    pct: int
    created_at: datetime
    record_count: int = 0
    total_messages: int = 0

    class Config:
        from_attributes = True


class ReportsListResponse(BaseModel):
    """Response for /api/reports"""
    reports: List[ReportDetail]
    total: int
    page: int
    page_size: int


# Summary statistics
class SummaryStats(BaseModel):
    """Summary statistics response for /api/rollup/summary"""
    total_messages: int
    total_reports: int
    pass_count: int
    fail_count: int
    pass_percentage: float
    fail_percentage: float
    disposition_none: int
    disposition_quarantine: int
    disposition_reject: int
    date_range_start: Optional[datetime]
    date_range_end: Optional[datetime]


# Source IP statistics
class SourceIPStats(BaseModel):
    """Statistics by source IP"""
    source_ip: str
    total_count: int
    pass_count: int
    fail_count: int
    pass_percentage: float
    report_count: int

    class Config:
        from_attributes = True


class SourceIPListResponse(BaseModel):
    """Response for /api/rollup/sources"""
    sources: List[SourceIPStats]
    total: int
    page: int
    page_size: int


# Alignment statistics
class AlignmentStats(BaseModel):
    """SPF and DKIM alignment statistics"""
    total_messages: int
    spf_pass: int
    spf_fail: int
    spf_other: int
    spf_pass_percentage: float
    dkim_pass: int
    dkim_fail: int
    dkim_other: int
    dkim_pass_percentage: float
    both_pass: int
    both_pass_percentage: float
    either_pass: int
    either_pass_percentage: float


# Timeline statistics
class TimelineStats(BaseModel):
    """Statistics for a specific date"""
    date: str
    total_messages: int
    pass_count: int
    fail_count: int
    report_count: int

    class Config:
        from_attributes = True


class TimelineListResponse(BaseModel):
    """Response for /api/rollup/timeline"""
    timeline: List[TimelineStats]
    total: int


# Manual operations
class IngestTriggerResponse(BaseModel):
    """Response for manual ingest trigger"""
    message: str
    reports_ingested: int
    emails_checked: int


class ProcessTriggerResponse(BaseModel):
    """Response for manual process trigger"""
    message: str
    reports_processed: int
    reports_failed: int


# Health check
class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    database: str


# Configuration status
class ConfigStatusResponse(BaseModel):
    """Configuration status response"""
    email_configured: bool
    email_host: Optional[str]
    email_folder: Optional[str]
    scheduler_running: bool
    background_jobs: List[str]


# Alerting
class AlertDetail(BaseModel):
    """Single alert details"""
    alert_type: str
    severity: str
    title: str
    message: str
    details: dict
    timestamp: datetime


class CheckAlertsResponse(BaseModel):
    """Response for alert check"""
    alerts_found: int
    alerts: List[AlertDetail]
    notifications_sent: int
    notification_channels: dict


class AlertConfigResponse(BaseModel):
    """Alert configuration status"""
    enabled: bool
    failure_warning_threshold: float
    failure_critical_threshold: float
    volume_spike_threshold: float
    volume_drop_threshold: float
    email_configured: bool
    slack_configured: bool
    discord_configured: bool
    teams_configured: bool
    webhook_configured: bool


# File upload
class UploadedFileDetail(BaseModel):
    """Details about an uploaded file"""
    filename: str
    status: str  # "uploaded", "duplicate", "error", "invalid"
    file_size: int
    content_hash: Optional[str] = None
    error_message: Optional[str] = None
    ingestion_record_id: Optional[int] = None


class UploadReportsResponse(BaseModel):
    """Response for bulk upload endpoint"""
    message: str
    total_files: int
    uploaded: int
    duplicates: int
    errors: int
    invalid_files: int
    files: List[UploadedFileDetail]
    auto_processed: bool
    reports_processed: Optional[int] = None
    reports_failed: Optional[int] = None


# Record-level details
class RecordDetailResponse(BaseModel):
    """Detailed information about a single DMARC record"""
    id: int
    source_ip: str
    count: int
    disposition: str

    # Authentication results
    dkim: Optional[str] = None
    dkim_domain: Optional[str] = None
    dkim_result: Optional[str] = None
    dkim_selector: Optional[str] = None

    spf: Optional[str] = None
    spf_domain: Optional[str] = None
    spf_result: Optional[str] = None
    spf_scope: Optional[str] = None

    # Email identifiers
    header_from: Optional[str] = None
    envelope_from: Optional[str] = None
    envelope_to: Optional[str] = None

    class Config:
        from_attributes = True


class ReportRecordsResponse(BaseModel):
    """Response for /api/reports/{id}/records"""
    report_id: int
    total: int
    page: int
    page_size: int
    records: List[RecordDetailResponse]
