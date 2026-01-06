from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import List, Optional


class RecordBase(BaseModel):
    source_ip: str
    count: int
    disposition: Optional[str] = None
    dkim_result: Optional[str] = None
    spf_result: Optional[str] = None
    envelope_to: Optional[str] = None
    envelope_from: Optional[str] = None
    header_from: Optional[str] = None
    dkim_domain: Optional[str] = None
    dkim_selector: Optional[str] = None
    dkim_auth_result: Optional[str] = None
    spf_domain: Optional[str] = None
    spf_scope: Optional[str] = None
    spf_auth_result: Optional[str] = None


class RecordCreate(RecordBase):
    pass


class RecordResponse(RecordBase):
    id: int
    report_id: int

    class Config:
        from_attributes = True


class ReportBase(BaseModel):
    report_id: str
    org_name: str
    email: Optional[str] = None
    extra_contact_info: Optional[str] = None
    date_begin: datetime
    date_end: datetime
    domain: str
    adkim: Optional[str] = None
    aspf: Optional[str] = None
    p: Optional[str] = None
    sp: Optional[str] = None
    pct: Optional[int] = None


class ReportCreate(ReportBase):
    records: List[RecordCreate]


class ReportResponse(ReportBase):
    id: int
    created_at: datetime
    records: List[RecordResponse] = []
    total_records: Optional[int] = None
    pass_count: Optional[int] = None
    fail_count: Optional[int] = None

    class Config:
        from_attributes = True


class ReportListResponse(BaseModel):
    reports: List[ReportResponse]
    total: int
    page: int
    page_size: int


class StatsSummary(BaseModel):
    total_reports: int
    total_messages: int
    pass_rate: float
    fail_rate: float


class StatsByDate(BaseModel):
    date: str
    pass_count: int
    fail_count: int
    total_count: int


class StatsByDomain(BaseModel):
    domain: str
    pass_count: int
    fail_count: int
    total_count: int


class StatsBySourceIP(BaseModel):
    source_ip: str
    count: int


class IngestResponse(BaseModel):
    message: str
    reports_processed: int
    emails_checked: int
