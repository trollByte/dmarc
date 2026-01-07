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
