"""
MTA-STS (Mail Transfer Agent Strict Transport Security) Monitoring Service.

Monitors MTA-STS policies and checks for:
- Valid MTA-STS DNS record (_mta-sts.domain)
- Valid MTA-STS policy file (https://mta-sts.domain/.well-known/mta-sts.txt)
- Policy compliance and configuration issues
"""

import dns.resolver
import httpx
import hashlib
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base
import uuid

logger = logging.getLogger(__name__)


class STSMode(str, Enum):
    """MTA-STS policy modes"""
    NONE = "none"
    TESTING = "testing"
    ENFORCE = "enforce"


class PolicyStatus(str, Enum):
    """MTA-STS policy status"""
    VALID = "valid"
    INVALID = "invalid"
    MISSING = "missing"
    EXPIRED = "expired"
    MISMATCH = "mismatch"


@dataclass
class STSRecord:
    """MTA-STS DNS TXT record"""
    version: str
    id: str
    raw: str


@dataclass
class STSPolicy:
    """MTA-STS policy file content"""
    version: str
    mode: STSMode
    mx: List[str]
    max_age: int
    raw: str


@dataclass
class MTASTSCheck:
    """Result of MTA-STS check for a domain"""
    domain: str
    has_record: bool
    has_policy: bool
    record: Optional[STSRecord]
    policy: Optional[STSPolicy]
    status: PolicyStatus
    mx_valid: bool
    issues: List[str]
    warnings: List[str]
    checked_at: datetime


class MTASTSMonitor(Base):
    """Tracked MTA-STS domains"""
    __tablename__ = "mta_sts_monitors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain = Column(String(255), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Last known state
    last_status = Column(String(20), nullable=True)
    last_mode = Column(String(20), nullable=True)
    last_policy_id = Column(String(100), nullable=True)
    last_policy_hash = Column(String(64), nullable=True)
    last_max_age = Column(Integer, nullable=True)
    last_mx_hosts = Column(Text, nullable=True)  # Comma-separated

    # Check results
    last_checked_at = Column(DateTime, nullable=True)
    last_change_at = Column(DateTime, nullable=True)
    consecutive_failures = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<MTASTSMonitor(domain={self.domain})>"


class MTASTSChangeLog(Base):
    """Log of MTA-STS changes"""
    __tablename__ = "mta_sts_change_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain = Column(String(255), nullable=False, index=True)
    change_type = Column(String(50), nullable=False)  # policy_added, policy_removed, mode_changed, mx_changed
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    details = Column(JSONB, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<MTASTSChangeLog(domain={self.domain}, change={self.change_type})>"


class MTASTSService:
    """Service for MTA-STS monitoring"""

    POLICY_URL_TEMPLATE = "https://mta-sts.{domain}/.well-known/mta-sts.txt"
    DNS_RECORD_PREFIX = "_mta-sts"

    def __init__(self, db: Session):
        self.db = db
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = 5
        self.resolver.lifetime = 10

    # ==================== Domain Management ====================

    def add_domain(self, domain: str) -> MTASTSMonitor:
        """Add a domain to MTA-STS monitoring"""
        existing = self.db.query(MTASTSMonitor).filter(
            MTASTSMonitor.domain == domain
        ).first()

        if existing:
            existing.is_active = True
            self.db.commit()
            return existing

        monitor = MTASTSMonitor(domain=domain)
        self.db.add(monitor)
        self.db.commit()
        self.db.refresh(monitor)

        # Initial check
        self._check_and_update(monitor)

        return monitor

    def remove_domain(self, domain: str) -> bool:
        """Remove domain from monitoring"""
        monitor = self.db.query(MTASTSMonitor).filter(
            MTASTSMonitor.domain == domain
        ).first()

        if monitor:
            monitor.is_active = False
            self.db.commit()
            return True
        return False

    def get_domains(self, active_only: bool = True) -> List[MTASTSMonitor]:
        """Get monitored domains"""
        query = self.db.query(MTASTSMonitor)
        if active_only:
            query = query.filter(MTASTSMonitor.is_active == True)
        return query.order_by(MTASTSMonitor.domain).all()

    # ==================== Checking ====================

    def check_domain(self, domain: str) -> MTASTSCheck:
        """Check MTA-STS for a single domain"""
        return self._perform_check(domain)

    def check_all_domains(self) -> Dict[str, MTASTSCheck]:
        """Check all monitored domains"""
        domains = self.get_domains(active_only=True)
        results = {}

        for monitor in domains:
            check = self._check_and_update(monitor)
            results[monitor.domain] = check

        return results

    def _check_and_update(self, monitor: MTASTSMonitor) -> MTASTSCheck:
        """Check domain and update monitor state"""
        check = self._perform_check(monitor.domain)

        # Detect changes
        if monitor.last_policy_id is not None or check.record is not None:
            self._detect_changes(monitor, check)

        # Update monitor
        monitor.last_status = check.status.value
        monitor.last_checked_at = check.checked_at

        if check.policy:
            monitor.last_mode = check.policy.mode.value
            monitor.last_max_age = check.policy.max_age
            monitor.last_mx_hosts = ",".join(check.policy.mx)
            monitor.last_policy_hash = hashlib.sha256(
                check.policy.raw.encode()
            ).hexdigest()

        if check.record:
            monitor.last_policy_id = check.record.id

        if check.status == PolicyStatus.VALID:
            monitor.consecutive_failures = 0
        else:
            monitor.consecutive_failures += 1

        self.db.commit()
        return check

    def _perform_check(self, domain: str) -> MTASTSCheck:
        """Perform MTA-STS check for a domain"""
        issues = []
        warnings = []
        record = None
        policy = None
        mx_valid = False

        # Check DNS record
        record = self._get_sts_record(domain)
        has_record = record is not None

        if not has_record:
            issues.append("No MTA-STS DNS record found")

        # Check policy file
        policy = self._get_sts_policy(domain)
        has_policy = policy is not None

        if not has_policy and has_record:
            issues.append("MTA-STS DNS record exists but policy file not found")

        # Validate policy
        if policy:
            # Check mode
            if policy.mode == STSMode.NONE:
                warnings.append("MTA-STS mode is 'none' - no protection")
            elif policy.mode == STSMode.TESTING:
                warnings.append("MTA-STS mode is 'testing' - not enforcing")

            # Check max_age
            if policy.max_age < 86400:
                warnings.append(f"max_age is very short ({policy.max_age}s < 1 day)")
            elif policy.max_age < 604800:
                warnings.append(f"max_age is short ({policy.max_age}s < 1 week)")

            # Validate MX hosts
            actual_mx = self._get_mx_records(domain)
            if actual_mx:
                mx_valid = self._validate_mx_hosts(policy.mx, actual_mx)
                if not mx_valid:
                    issues.append("MX hosts in policy don't match actual MX records")

        # Determine status
        if not has_record and not has_policy:
            status = PolicyStatus.MISSING
        elif has_record and not has_policy:
            status = PolicyStatus.INVALID
        elif not mx_valid and policy:
            status = PolicyStatus.MISMATCH
        elif issues:
            status = PolicyStatus.INVALID
        else:
            status = PolicyStatus.VALID

        return MTASTSCheck(
            domain=domain,
            has_record=has_record,
            has_policy=has_policy,
            record=record,
            policy=policy,
            status=status,
            mx_valid=mx_valid,
            issues=issues,
            warnings=warnings,
            checked_at=datetime.utcnow(),
        )

    def _get_sts_record(self, domain: str) -> Optional[STSRecord]:
        """Get MTA-STS DNS TXT record"""
        try:
            record_name = f"{self.DNS_RECORD_PREFIX}.{domain}"
            answers = self.resolver.resolve(record_name, 'TXT')

            for rdata in answers:
                txt = rdata.to_text().strip('"')

                # Parse v=STSv1; id=xxx
                if "v=STSv1" in txt:
                    parts = dict(
                        p.split("=", 1) for p in txt.split(";")
                        if "=" in p
                    )
                    return STSRecord(
                        version=parts.get("v", "STSv1").strip(),
                        id=parts.get("id", "").strip(),
                        raw=txt,
                    )
        except Exception as e:
            logger.debug(f"Failed to get MTA-STS record for {domain}: {e}")
        return None

    def _get_sts_policy(self, domain: str) -> Optional[STSPolicy]:
        """Get MTA-STS policy file"""
        try:
            url = self.POLICY_URL_TEMPLATE.format(domain=domain)

            with httpx.Client(timeout=10, follow_redirects=True) as client:
                response = client.get(url)

                if response.status_code == 200:
                    return self._parse_policy(response.text)
        except Exception as e:
            logger.debug(f"Failed to get MTA-STS policy for {domain}: {e}")
        return None

    def _parse_policy(self, content: str) -> Optional[STSPolicy]:
        """Parse MTA-STS policy file content"""
        try:
            lines = content.strip().split("\n")
            policy_dict: Dict[str, Any] = {"mx": []}

            for line in lines:
                line = line.strip()
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip()

                    if key == "mx":
                        policy_dict["mx"].append(value)
                    else:
                        policy_dict[key] = value

            mode = STSMode(policy_dict.get("mode", "none"))
            max_age = int(policy_dict.get("max_age", 0))

            return STSPolicy(
                version=policy_dict.get("version", "STSv1"),
                mode=mode,
                mx=policy_dict["mx"],
                max_age=max_age,
                raw=content,
            )
        except Exception as e:
            logger.debug(f"Failed to parse MTA-STS policy: {e}")
        return None

    def _get_mx_records(self, domain: str) -> List[str]:
        """Get MX records for domain"""
        try:
            answers = self.resolver.resolve(domain, 'MX')
            return [str(rdata.exchange).rstrip('.') for rdata in answers]
        except Exception:
            return []

    def _validate_mx_hosts(self, policy_mx: List[str], actual_mx: List[str]) -> bool:
        """Validate that actual MX hosts match policy patterns"""
        for actual in actual_mx:
            matched = False
            for pattern in policy_mx:
                if pattern.startswith("*."):
                    # Wildcard match
                    suffix = pattern[1:]  # Remove *
                    if actual.endswith(suffix) or actual == pattern[2:]:
                        matched = True
                        break
                elif actual.lower() == pattern.lower():
                    matched = True
                    break

            if not matched:
                return False
        return True

    def _detect_changes(self, monitor: MTASTSMonitor, check: MTASTSCheck):
        """Detect and log changes"""
        changes = []

        # Policy added
        if monitor.last_policy_id is None and check.record:
            changes.append({
                "type": "policy_added",
                "old": None,
                "new": check.record.id,
            })

        # Policy removed
        elif monitor.last_policy_id and not check.record:
            changes.append({
                "type": "policy_removed",
                "old": monitor.last_policy_id,
                "new": None,
            })

        # Policy ID changed
        elif check.record and monitor.last_policy_id != check.record.id:
            changes.append({
                "type": "policy_updated",
                "old": monitor.last_policy_id,
                "new": check.record.id,
            })

        # Mode changed
        if check.policy and monitor.last_mode != check.policy.mode.value:
            changes.append({
                "type": "mode_changed",
                "old": monitor.last_mode,
                "new": check.policy.mode.value,
            })

        # MX hosts changed
        if check.policy:
            new_mx = ",".join(sorted(check.policy.mx))
            old_mx = monitor.last_mx_hosts or ""
            if old_mx and new_mx != ",".join(sorted(old_mx.split(","))):
                changes.append({
                    "type": "mx_changed",
                    "old": old_mx,
                    "new": new_mx,
                })

        # Log changes
        for change in changes:
            log = MTASTSChangeLog(
                domain=monitor.domain,
                change_type=change["type"],
                old_value=str(change["old"]) if change["old"] else None,
                new_value=str(change["new"]) if change["new"] else None,
                details=change,
            )
            self.db.add(log)
            monitor.last_change_at = datetime.utcnow()

    # ==================== History ====================

    def get_changes(
        self,
        domain: Optional[str] = None,
        days: int = 30,
        limit: int = 100,
    ) -> List[MTASTSChangeLog]:
        """Get MTA-STS change history"""
        since = datetime.utcnow() - timedelta(days=days)
        query = self.db.query(MTASTSChangeLog).filter(
            MTASTSChangeLog.detected_at >= since
        )

        if domain:
            query = query.filter(MTASTSChangeLog.domain == domain)

        return query.order_by(MTASTSChangeLog.detected_at.desc()).limit(limit).all()

    # ==================== Reporting ====================

    def generate_report(self, domain: str) -> Dict[str, Any]:
        """Generate MTA-STS report for a domain"""
        check = self._perform_check(domain)

        return {
            "domain": domain,
            "checked_at": check.checked_at.isoformat(),
            "status": check.status.value,
            "has_mta_sts": check.has_record and check.has_policy,
            "record": {
                "found": check.has_record,
                "version": check.record.version if check.record else None,
                "id": check.record.id if check.record else None,
            },
            "policy": {
                "found": check.has_policy,
                "mode": check.policy.mode.value if check.policy else None,
                "mx_hosts": check.policy.mx if check.policy else [],
                "max_age_seconds": check.policy.max_age if check.policy else None,
                "max_age_days": check.policy.max_age // 86400 if check.policy else None,
            },
            "mx_validation": {
                "valid": check.mx_valid,
            },
            "issues": check.issues,
            "warnings": check.warnings,
            "recommendations": self._get_recommendations(check),
        }

    def _get_recommendations(self, check: MTASTSCheck) -> List[str]:
        """Get recommendations based on check results"""
        recs = []

        if not check.has_record:
            recs.append("Add MTA-STS DNS TXT record: _mta-sts.domain TXT \"v=STSv1; id=YYYYMMDD\"")

        if not check.has_policy:
            recs.append("Create policy file at https://mta-sts.domain/.well-known/mta-sts.txt")

        if check.policy:
            if check.policy.mode == STSMode.NONE:
                recs.append("Change mode from 'none' to 'testing' to start monitoring")
            elif check.policy.mode == STSMode.TESTING:
                recs.append("Once confident, change mode from 'testing' to 'enforce'")

            if check.policy.max_age < 604800:
                recs.append("Consider increasing max_age to at least 604800 (1 week)")

        if not check.mx_valid and check.policy:
            recs.append("Update policy MX patterns to match your actual MX records")

        return recs
