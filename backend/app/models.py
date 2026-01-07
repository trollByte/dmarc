from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class IngestedReport(Base):
    """Track ingested DMARC report files"""
    __tablename__ = "ingested_reports"

    id = Column(Integer, primary_key=True, index=True)

    # Email metadata
    message_id = Column(String(500), index=True, nullable=True)
    received_at = Column(DateTime, nullable=False)

    # File information
    filename = Column(String(500), nullable=False)
    content_hash = Column(String(64), unique=True, index=True, nullable=False)
    file_size = Column(Integer, nullable=False)
    storage_path = Column(String(1000), nullable=False)

    # Processing status
    status = Column(String(50), nullable=False, index=True)  # pending, processing, completed, failed
    parse_error = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<IngestedReport(id={self.id}, filename={self.filename}, status={self.status})>"


class DmarcReport(Base):
    """Parsed DMARC aggregate report"""
    __tablename__ = "dmarc_reports"

    id = Column(Integer, primary_key=True, index=True)

    # Link to ingested report
    ingested_report_id = Column(Integer, ForeignKey("ingested_reports.id"), nullable=True)

    # Report metadata
    report_id = Column(String(500), unique=True, index=True, nullable=False)
    org_name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), nullable=True)
    extra_contact_info = Column(String(500), nullable=True)

    # Date range
    date_begin = Column(DateTime, nullable=False, index=True)
    date_end = Column(DateTime, nullable=False, index=True)

    # Policy published
    domain = Column(String(255), nullable=False, index=True)
    adkim = Column(String(20), nullable=True)  # DKIM alignment mode
    aspf = Column(String(20), nullable=True)   # SPF alignment mode
    p = Column(String(20), nullable=False)     # Policy for domain
    sp = Column(String(20), nullable=True)     # Policy for subdomains
    pct = Column(Integer, default=100)         # Percentage

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    records = relationship("DmarcRecord", back_populates="report", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<DmarcReport(id={self.id}, report_id={self.report_id}, domain={self.domain})>"


class DmarcRecord(Base):
    """Individual DMARC record from a report"""
    __tablename__ = "dmarc_records"

    id = Column(Integer, primary_key=True, index=True)

    # Link to report
    report_id = Column(Integer, ForeignKey("dmarc_reports.id"), nullable=False)

    # Source information
    source_ip = Column(String(45), nullable=False, index=True)  # IPv4 or IPv6
    count = Column(Integer, nullable=False)

    # Policy evaluated
    disposition = Column(String(20), nullable=True)  # none, quarantine, reject
    dkim = Column(String(20), nullable=True)         # pass, fail
    spf = Column(String(20), nullable=True)          # pass, fail

    # Identifiers
    header_from = Column(String(255), nullable=True)
    envelope_from = Column(String(255), nullable=True)
    envelope_to = Column(String(255), nullable=True)

    # Auth results - store as JSON-like text for multiple results
    # For simplicity, we'll store first DKIM and SPF result
    dkim_domain = Column(String(255), nullable=True)
    dkim_result = Column(String(20), nullable=True)
    dkim_selector = Column(String(255), nullable=True)
    spf_domain = Column(String(255), nullable=True)
    spf_result = Column(String(20), nullable=True)
    spf_scope = Column(String(50), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    report = relationship("DmarcReport", back_populates="records")

    def __repr__(self):
        return f"<DmarcRecord(id={self.id}, source_ip={self.source_ip}, count={self.count})>"
