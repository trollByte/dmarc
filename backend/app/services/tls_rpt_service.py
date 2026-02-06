"""
TLS-RPT (TLS Reporting) Service.

Parses and processes TLS-RPT reports (RFC 8460) which provide
feedback about TLS negotiation failures during email delivery.

Report format: JSON
DNS record: _smtp._tls.domain TXT "v=TLSRPTv1; rua=mailto:reports@domain"
"""

import json
import gzip
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
import hashlib

from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base
import uuid

logger = logging.getLogger(__name__)


class ResultType(str, Enum):
    """TLS-RPT result types"""
    STARTTLS_NOT_SUPPORTED = "starttls-not-supported"
    CERTIFICATE_HOST_MISMATCH = "certificate-host-mismatch"
    CERTIFICATE_EXPIRED = "certificate-expired"
    CERTIFICATE_NOT_TRUSTED = "certificate-not-trusted"
    VALIDATION_FAILURE = "validation-failure"
    TLSA_INVALID = "tlsa-invalid"
    DNSSEC_INVALID = "dnssec-invalid"
    DANE_REQUIRED = "dane-required"
    STS_POLICY_FETCH_ERROR = "sts-policy-fetch-error"
    STS_POLICY_INVALID = "sts-policy-invalid"
    STS_WEBPKI_INVALID = "sts-webpki-invalid"


class PolicyType(str, Enum):
    """TLS policy types"""
    TLSA = "tlsa"
    STS = "sts"
    NO_POLICY = "no-policy-found"


@dataclass
class TLSPolicy:
    """TLS policy from report"""
    policy_type: PolicyType
    policy_string: List[str]
    policy_domain: str
    mx_host: Optional[str] = None


@dataclass
class FailureDetail:
    """Failure detail from report"""
    result_type: str
    sending_mta_ip: str
    receiving_mx_hostname: str
    receiving_ip: Optional[str] = None
    failed_session_count: int = 0
    additional_info: Optional[str] = None
    failure_reason_code: Optional[str] = None


@dataclass
class TLSRPTSummary:
    """Summary of parsed TLS-RPT"""
    report_id: str
    organization_name: str
    date_range_begin: datetime
    date_range_end: datetime
    contact_info: Optional[str]
    policies: List[TLSPolicy]
    failure_details: List[FailureDetail]
    total_successful_sessions: int
    total_failed_sessions: int


class TLSReport(Base):
    """Stored TLS-RPT reports"""
    __tablename__ = "tls_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(String(255), unique=True, nullable=False, index=True)
    report_hash = Column(String(64), unique=True, nullable=False)

    # Reporter info
    organization_name = Column(String(255), nullable=False)
    contact_info = Column(String(255), nullable=True)

    # Date range
    date_range_begin = Column(DateTime, nullable=False, index=True)
    date_range_end = Column(DateTime, nullable=False)

    # Policy domain
    policy_domain = Column(String(255), nullable=False, index=True)
    policy_type = Column(String(20), nullable=False)

    # Counts
    successful_session_count = Column(Integer, default=0, nullable=False)
    failed_session_count = Column(Integer, default=0, nullable=False)

    # Full report data
    raw_report = Column(JSONB, nullable=False)
    policies = Column(JSONB, nullable=True)
    failure_details = Column(JSONB, nullable=True)

    # Metadata
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    source_ip = Column(String(45), nullable=True)
    filename = Column(String(255), nullable=True)

    def __repr__(self):
        return f"<TLSReport(id={self.report_id}, org={self.organization_name})>"


class TLSFailureSummary(Base):
    """Aggregated TLS failure data"""
    __tablename__ = "tls_failure_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_domain = Column(String(255), nullable=False, index=True)
    result_type = Column(String(50), nullable=False, index=True)
    receiving_mx_hostname = Column(String(255), nullable=True)
    sending_mta_ip = Column(String(45), nullable=True)

    # Counts
    failure_count = Column(Integer, default=0, nullable=False)
    report_count = Column(Integer, default=0, nullable=False)

    # Time period
    first_seen = Column(DateTime, nullable=False)
    last_seen = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<TLSFailureSummary(domain={self.policy_domain}, type={self.result_type})>"


class TLSRPTService:
    """Service for TLS-RPT processing"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== Report Parsing ====================

    def parse_report(self, data: bytes, filename: Optional[str] = None) -> TLSRPTSummary:
        """
        Parse a TLS-RPT report from raw bytes.

        Supports:
        - Raw JSON
        - Gzipped JSON
        """
        # Try to decompress if gzipped
        try:
            if data[:2] == b'\x1f\x8b':  # Gzip magic number
                data = gzip.decompress(data)
        except Exception:
            logger.debug("Failed to decompress gzipped TLS-RPT data, trying as raw JSON")

        # Parse JSON
        try:
            report_json = json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"Failed to parse TLS-RPT JSON: {e}")

        return self._parse_json_report(report_json)

    def _parse_json_report(self, report: Dict[str, Any]) -> TLSRPTSummary:
        """Parse JSON report structure"""
        # Extract organization info
        org_name = report.get("organization-name", "Unknown")
        contact = report.get("contact-info")
        report_id = report.get("report-id", str(uuid.uuid4()))

        # Parse date range
        date_range = report.get("date-range", {})
        begin = self._parse_datetime(date_range.get("start-datetime"))
        end = self._parse_datetime(date_range.get("end-datetime"))

        # Parse policies
        policies = []
        failure_details = []
        total_success = 0
        total_failed = 0

        for policy_data in report.get("policies", []):
            # Parse policy
            policy = TLSPolicy(
                policy_type=PolicyType(policy_data.get("policy", {}).get("policy-type", "no-policy-found")),
                policy_string=policy_data.get("policy", {}).get("policy-string", []),
                policy_domain=policy_data.get("policy", {}).get("policy-domain", ""),
                mx_host=policy_data.get("policy", {}).get("mx-host"),
            )
            policies.append(policy)

            # Parse summary
            summary = policy_data.get("summary", {})
            total_success += summary.get("total-successful-session-count", 0)
            total_failed += summary.get("total-failure-session-count", 0)

            # Parse failure details
            for detail in policy_data.get("failure-details", []):
                fd = FailureDetail(
                    result_type=detail.get("result-type", "validation-failure"),
                    sending_mta_ip=detail.get("sending-mta-ip", ""),
                    receiving_mx_hostname=detail.get("receiving-mx-hostname", ""),
                    receiving_ip=detail.get("receiving-ip"),
                    failed_session_count=detail.get("failed-session-count", 0),
                    additional_info=detail.get("additional-information"),
                    failure_reason_code=detail.get("failure-reason-code"),
                )
                failure_details.append(fd)

        return TLSRPTSummary(
            report_id=report_id,
            organization_name=org_name,
            date_range_begin=begin,
            date_range_end=end,
            contact_info=contact,
            policies=policies,
            failure_details=failure_details,
            total_successful_sessions=total_success,
            total_failed_sessions=total_failed,
        )

    def _parse_datetime(self, dt_str: Optional[str]) -> datetime:
        """Parse datetime from report"""
        if not dt_str:
            return datetime.utcnow()

        # Try common formats
        formats = [
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(dt_str.replace("+00:00", "Z"), fmt)
            except ValueError:
                continue

        return datetime.utcnow()

    # ==================== Report Storage ====================

    def store_report(
        self,
        data: bytes,
        filename: Optional[str] = None,
        source_ip: Optional[str] = None,
    ) -> TLSReport:
        """Store a TLS-RPT report"""
        # Parse report
        summary = self.parse_report(data, filename)

        # Calculate hash for deduplication
        report_hash = hashlib.sha256(data).hexdigest()

        # Check for duplicate
        existing = self.db.query(TLSReport).filter(
            TLSReport.report_hash == report_hash
        ).first()

        if existing:
            return existing

        # Get primary policy domain
        policy_domain = summary.policies[0].policy_domain if summary.policies else "unknown"
        policy_type = summary.policies[0].policy_type.value if summary.policies else "no-policy-found"

        # Create report record
        report = TLSReport(
            report_id=summary.report_id,
            report_hash=report_hash,
            organization_name=summary.organization_name,
            contact_info=summary.contact_info,
            date_range_begin=summary.date_range_begin,
            date_range_end=summary.date_range_end,
            policy_domain=policy_domain,
            policy_type=policy_type,
            successful_session_count=summary.total_successful_sessions,
            failed_session_count=summary.total_failed_sessions,
            raw_report=json.loads(data.decode('utf-8')),
            policies=[
                {
                    "policy_type": p.policy_type.value,
                    "policy_domain": p.policy_domain,
                    "policy_string": p.policy_string,
                    "mx_host": p.mx_host,
                }
                for p in summary.policies
            ],
            failure_details=[
                {
                    "result_type": f.result_type,
                    "sending_mta_ip": f.sending_mta_ip,
                    "receiving_mx_hostname": f.receiving_mx_hostname,
                    "receiving_ip": f.receiving_ip,
                    "failed_session_count": f.failed_session_count,
                    "additional_info": f.additional_info,
                    "failure_reason_code": f.failure_reason_code,
                }
                for f in summary.failure_details
            ],
            source_ip=source_ip,
            filename=filename,
        )

        self.db.add(report)

        # Update failure summaries
        self._update_failure_summaries(summary)

        self.db.commit()
        self.db.refresh(report)

        return report

    def _update_failure_summaries(self, summary: TLSRPTSummary):
        """Update aggregated failure summaries"""
        for policy in summary.policies:
            for detail in summary.failure_details:
                existing = self.db.query(TLSFailureSummary).filter(
                    TLSFailureSummary.policy_domain == policy.policy_domain,
                    TLSFailureSummary.result_type == detail.result_type,
                    TLSFailureSummary.receiving_mx_hostname == detail.receiving_mx_hostname,
                ).first()

                if existing:
                    existing.failure_count += detail.failed_session_count
                    existing.report_count += 1
                    existing.last_seen = datetime.utcnow()
                else:
                    fs = TLSFailureSummary(
                        policy_domain=policy.policy_domain,
                        result_type=detail.result_type,
                        receiving_mx_hostname=detail.receiving_mx_hostname,
                        sending_mta_ip=detail.sending_mta_ip,
                        failure_count=detail.failed_session_count,
                        report_count=1,
                        first_seen=summary.date_range_begin,
                        last_seen=summary.date_range_end,
                    )
                    self.db.add(fs)

    # ==================== Queries ====================

    def get_reports(
        self,
        domain: Optional[str] = None,
        days: int = 30,
        limit: int = 100,
    ) -> List[TLSReport]:
        """Get TLS-RPT reports"""
        since = datetime.utcnow() - timedelta(days=days)
        query = self.db.query(TLSReport).filter(
            TLSReport.date_range_begin >= since
        )

        if domain:
            query = query.filter(TLSReport.policy_domain == domain)

        return query.order_by(TLSReport.date_range_begin.desc()).limit(limit).all()

    def get_failures(
        self,
        domain: Optional[str] = None,
        result_type: Optional[str] = None,
        days: int = 30,
    ) -> List[TLSFailureSummary]:
        """Get failure summaries"""
        since = datetime.utcnow() - timedelta(days=days)
        query = self.db.query(TLSFailureSummary).filter(
            TLSFailureSummary.last_seen >= since
        )

        if domain:
            query = query.filter(TLSFailureSummary.policy_domain == domain)
        if result_type:
            query = query.filter(TLSFailureSummary.result_type == result_type)

        return query.order_by(TLSFailureSummary.failure_count.desc()).all()

    def get_domain_stats(self, domain: str, days: int = 30) -> Dict[str, Any]:
        """Get TLS statistics for a domain"""
        since = datetime.utcnow() - timedelta(days=days)

        reports = self.db.query(TLSReport).filter(
            TLSReport.policy_domain == domain,
            TLSReport.date_range_begin >= since
        ).all()

        total_success = sum(r.successful_session_count for r in reports)
        total_failed = sum(r.failed_session_count for r in reports)
        total_sessions = total_success + total_failed

        # Group failures by type
        failures_by_type = {}
        for report in reports:
            for detail in report.failure_details or []:
                rt = detail.get("result_type", "unknown")
                if rt not in failures_by_type:
                    failures_by_type[rt] = 0
                failures_by_type[rt] += detail.get("failed_session_count", 0)

        return {
            "domain": domain,
            "period_days": days,
            "report_count": len(reports),
            "total_sessions": total_sessions,
            "successful_sessions": total_success,
            "failed_sessions": total_failed,
            "success_rate": (total_success / total_sessions * 100) if total_sessions > 0 else 100,
            "failures_by_type": failures_by_type,
            "unique_reporters": len(set(r.organization_name for r in reports)),
        }

    def get_failure_trends(
        self,
        domain: Optional[str] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get daily failure trends"""
        since = datetime.utcnow() - timedelta(days=days)

        query = self.db.query(
            func.date(TLSReport.date_range_begin).label('date'),
            func.sum(TLSReport.successful_session_count).label('success'),
            func.sum(TLSReport.failed_session_count).label('failed'),
            func.count(TLSReport.id).label('reports'),
        ).filter(
            TLSReport.date_range_begin >= since
        )

        if domain:
            query = query.filter(TLSReport.policy_domain == domain)

        results = query.group_by(
            func.date(TLSReport.date_range_begin)
        ).order_by(
            func.date(TLSReport.date_range_begin)
        ).all()

        return [
            {
                "date": str(r.date),
                "successful_sessions": r.success or 0,
                "failed_sessions": r.failed or 0,
                "report_count": r.reports,
            }
            for r in results
        ]

    # ==================== DNS Record ====================

    def check_tlsrpt_record(self, domain: str) -> Dict[str, Any]:
        """Check TLS-RPT DNS record for a domain"""
        import dns.resolver

        resolver = dns.resolver.Resolver()
        resolver.timeout = 5

        result = {
            "domain": domain,
            "has_record": False,
            "record": None,
            "rua": [],
            "issues": [],
        }

        try:
            record_name = f"_smtp._tls.{domain}"
            answers = resolver.resolve(record_name, 'TXT')

            for rdata in answers:
                txt = rdata.to_text().strip('"')
                if "v=TLSRPTv1" in txt:
                    result["has_record"] = True
                    result["record"] = txt

                    # Parse rua
                    parts = txt.split(";")
                    for part in parts:
                        part = part.strip()
                        if part.startswith("rua="):
                            ruas = part[4:].split(",")
                            result["rua"] = [r.strip() for r in ruas]

        except Exception as e:
            result["issues"].append(f"Failed to query TLS-RPT record: {str(e)}")

        return result

    def generate_tlsrpt_record(
        self,
        domain: str,
        rua: List[str],
    ) -> Dict[str, str]:
        """Generate TLS-RPT DNS record"""
        rua_str = ",".join(rua)

        return {
            "domain": domain,
            "record_name": f"_smtp._tls.{domain}",
            "record_type": "TXT",
            "record_value": f"v=TLSRPTv1; rua={rua_str}",
            "ttl": 3600,
        }
