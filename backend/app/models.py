from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class ProcessedEmail(Base):
    """Track processed emails for idempotency"""
    __tablename__ = "processed_emails"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(500), unique=True, index=True, nullable=False)
    subject = Column(String(500))
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ProcessedEmail(message_id={self.message_id})>"


class Report(Base):
    """DMARC Aggregate Report"""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)

    # Report metadata
    report_id = Column(String(500), unique=True, index=True, nullable=False)
    org_name = Column(String(255), nullable=False)
    email = Column(String(255))
    extra_contact_info = Column(Text)

    # Date range
    date_begin = Column(DateTime, nullable=False, index=True)
    date_end = Column(DateTime, nullable=False, index=True)

    # Policy published
    domain = Column(String(255), nullable=False, index=True)
    adkim = Column(String(10))  # DKIM alignment mode (r/s)
    aspf = Column(String(10))   # SPF alignment mode (r/s)
    p = Column(String(20))      # Policy for domain (none/quarantine/reject)
    sp = Column(String(20))     # Policy for subdomains
    pct = Column(Integer)       # Percentage of messages to filter

    # Processing metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    records = relationship("Record", back_populates="report", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Report(id={self.id}, org={self.org_name}, domain={self.domain})>"


class Record(Base):
    """Individual DMARC record from a report"""
    __tablename__ = "records"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=False, index=True)

    # Row/Source
    source_ip = Column(String(45), nullable=False, index=True)  # IPv4 or IPv6
    count = Column(Integer, nullable=False)

    # Policy evaluated
    disposition = Column(String(20))  # none/quarantine/reject
    dkim_result = Column(String(20))  # pass/fail
    spf_result = Column(String(20))   # pass/fail

    # Identifiers
    envelope_to = Column(String(255))
    envelope_from = Column(String(255))
    header_from = Column(String(255), index=True)

    # Auth results - DKIM
    dkim_domain = Column(String(255))
    dkim_selector = Column(String(255))
    dkim_auth_result = Column(String(20))

    # Auth results - SPF
    spf_domain = Column(String(255))
    spf_scope = Column(String(20))
    spf_auth_result = Column(String(20))

    # Relationships
    report = relationship("Report", back_populates="records")

    def __repr__(self):
        return f"<Record(id={self.id}, source_ip={self.source_ip}, count={self.count})>"
