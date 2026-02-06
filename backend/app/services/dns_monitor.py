"""
DNS Change Monitoring Service.

Monitors DNS records for changes and triggers alerts when:
- DMARC policy changes
- SPF record changes
- DKIM selectors change
- MX records change
"""

import dns.resolver
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base
import uuid

logger = logging.getLogger(__name__)


class RecordType(str, Enum):
    """DNS record types to monitor"""
    DMARC = "dmarc"
    SPF = "spf"
    DKIM = "dkim"
    MX = "mx"
    A = "a"
    AAAA = "aaaa"
    NS = "ns"
    TXT = "txt"


class ChangeType(str, Enum):
    """Types of DNS changes"""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


@dataclass
class DNSChange:
    """Detected DNS change"""
    domain: str
    record_type: str
    change_type: ChangeType
    old_value: Optional[str]
    new_value: Optional[str]
    detected_at: datetime


class MonitoredDomain(Base):
    """Domains being monitored for DNS changes"""
    __tablename__ = "monitored_domains"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain = Column(String(255), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # What to monitor
    monitor_dmarc = Column(Boolean, default=True, nullable=False)
    monitor_spf = Column(Boolean, default=True, nullable=False)
    monitor_dkim = Column(Boolean, default=False, nullable=False)
    monitor_mx = Column(Boolean, default=False, nullable=False)

    # DKIM selectors to check (comma-separated)
    dkim_selectors = Column(String(500), nullable=True)

    # Last known values (hashes)
    last_dmarc_hash = Column(String(64), nullable=True)
    last_spf_hash = Column(String(64), nullable=True)
    last_dkim_hash = Column(String(64), nullable=True)
    last_mx_hash = Column(String(64), nullable=True)

    # Timestamps
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<MonitoredDomain(domain={self.domain})>"


class DNSChangeLog(Base):
    """Log of detected DNS changes"""
    __tablename__ = "dns_change_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain = Column(String(255), nullable=False, index=True)
    record_type = Column(String(20), nullable=False, index=True)
    change_type = Column(String(20), nullable=False)

    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    # Alert status
    alert_sent = Column(Boolean, default=False, nullable=False)
    acknowledged = Column(Boolean, default=False, nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)

    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<DNSChangeLog(domain={self.domain}, type={self.record_type}, change={self.change_type})>"


class DNSMonitorService:
    """Service for monitoring DNS changes"""

    def __init__(self, db: Session):
        self.db = db
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = 5
        self.resolver.lifetime = 10

    # ==================== Domain Management ====================

    def add_domain(
        self,
        domain: str,
        monitor_dmarc: bool = True,
        monitor_spf: bool = True,
        monitor_dkim: bool = False,
        monitor_mx: bool = False,
        dkim_selectors: Optional[List[str]] = None,
    ) -> MonitoredDomain:
        """Add a domain to monitoring"""
        existing = self.db.query(MonitoredDomain).filter(
            MonitoredDomain.domain == domain
        ).first()

        if existing:
            existing.is_active = True
            existing.monitor_dmarc = monitor_dmarc
            existing.monitor_spf = monitor_spf
            existing.monitor_dkim = monitor_dkim
            existing.monitor_mx = monitor_mx
            if dkim_selectors:
                existing.dkim_selectors = ",".join(dkim_selectors)
            self.db.commit()
            return existing

        monitored = MonitoredDomain(
            domain=domain,
            monitor_dmarc=monitor_dmarc,
            monitor_spf=monitor_spf,
            monitor_dkim=monitor_dkim,
            monitor_mx=monitor_mx,
            dkim_selectors=",".join(dkim_selectors) if dkim_selectors else None,
        )

        self.db.add(monitored)
        self.db.commit()
        self.db.refresh(monitored)

        # Initial snapshot
        self._take_snapshot(monitored)

        return monitored

    def remove_domain(self, domain: str) -> bool:
        """Remove domain from monitoring"""
        monitored = self.db.query(MonitoredDomain).filter(
            MonitoredDomain.domain == domain
        ).first()

        if monitored:
            monitored.is_active = False
            self.db.commit()
            return True
        return False

    def get_domains(self, active_only: bool = True) -> List[MonitoredDomain]:
        """Get monitored domains"""
        query = self.db.query(MonitoredDomain)
        if active_only:
            query = query.filter(MonitoredDomain.is_active == True)
        return query.order_by(MonitoredDomain.domain).all()

    # ==================== Monitoring ====================

    def check_domain(self, domain: str) -> List[DNSChange]:
        """Check a single domain for changes"""
        monitored = self.db.query(MonitoredDomain).filter(
            MonitoredDomain.domain == domain,
            MonitoredDomain.is_active == True
        ).first()

        if not monitored:
            return []

        return self._check_monitored(monitored)

    def check_all_domains(self) -> Dict[str, List[DNSChange]]:
        """Check all active domains for changes"""
        domains = self.get_domains(active_only=True)
        results = {}

        for monitored in domains:
            changes = self._check_monitored(monitored)
            if changes:
                results[monitored.domain] = changes

        return results

    def _check_monitored(self, monitored: MonitoredDomain) -> List[DNSChange]:
        """Check a monitored domain for changes"""
        changes = []

        if monitored.monitor_dmarc:
            change = self._check_dmarc(monitored)
            if change:
                changes.append(change)

        if monitored.monitor_spf:
            change = self._check_spf(monitored)
            if change:
                changes.append(change)

        if monitored.monitor_mx:
            change = self._check_mx(monitored)
            if change:
                changes.append(change)

        if monitored.monitor_dkim and monitored.dkim_selectors:
            dkim_changes = self._check_dkim(monitored)
            changes.extend(dkim_changes)

        monitored.last_checked_at = datetime.utcnow()
        self.db.commit()

        return changes

    def _check_dmarc(self, monitored: MonitoredDomain) -> Optional[DNSChange]:
        """Check DMARC record for changes"""
        record = self._get_txt_record(f"_dmarc.{monitored.domain}")
        current_hash = self._hash_value(record) if record else None

        if current_hash != monitored.last_dmarc_hash:
            old_value = self._get_stored_value(monitored.domain, "dmarc")
            change = self._log_change(
                monitored.domain,
                RecordType.DMARC,
                monitored.last_dmarc_hash,
                current_hash,
                old_value,
                record
            )
            monitored.last_dmarc_hash = current_hash
            return change

        return None

    def _check_spf(self, monitored: MonitoredDomain) -> Optional[DNSChange]:
        """Check SPF record for changes"""
        record = self._get_spf_record(monitored.domain)
        current_hash = self._hash_value(record) if record else None

        if current_hash != monitored.last_spf_hash:
            old_value = self._get_stored_value(monitored.domain, "spf")
            change = self._log_change(
                monitored.domain,
                RecordType.SPF,
                monitored.last_spf_hash,
                current_hash,
                old_value,
                record
            )
            monitored.last_spf_hash = current_hash
            return change

        return None

    def _check_mx(self, monitored: MonitoredDomain) -> Optional[DNSChange]:
        """Check MX records for changes"""
        records = self._get_mx_records(monitored.domain)
        record_str = ",".join(sorted(records)) if records else None
        current_hash = self._hash_value(record_str) if record_str else None

        if current_hash != monitored.last_mx_hash:
            old_value = self._get_stored_value(monitored.domain, "mx")
            change = self._log_change(
                monitored.domain,
                RecordType.MX,
                monitored.last_mx_hash,
                current_hash,
                old_value,
                record_str
            )
            monitored.last_mx_hash = current_hash
            return change

        return None

    # Common DKIM selectors to check when none are explicitly configured
    DEFAULT_DKIM_SELECTORS = ["google", "default", "selector1", "selector2"]

    def _check_dkim(self, monitored: MonitoredDomain) -> List[DNSChange]:
        """Check DKIM records for changes across all configured selectors."""
        changes = []
        selectors = (
            [s.strip() for s in monitored.dkim_selectors.split(",") if s.strip()]
            if monitored.dkim_selectors
            else self.DEFAULT_DKIM_SELECTORS
        )

        # Build combined DKIM value from all selectors
        dkim_parts = []
        for selector in selectors:
            record = self._get_txt_record(f"{selector}._domainkey.{monitored.domain}")
            if record:
                dkim_parts.append(f"{selector}={record}")

        combined = ";".join(sorted(dkim_parts)) if dkim_parts else None
        current_hash = self._hash_value(combined) if combined else None

        if current_hash != monitored.last_dkim_hash:
            old_value = self._get_stored_value(monitored.domain, "dkim")
            change = self._log_change(
                monitored.domain,
                RecordType.DKIM,
                monitored.last_dkim_hash,
                current_hash,
                old_value,
                combined,
            )
            monitored.last_dkim_hash = current_hash
            changes.append(change)

        return changes

    def _take_snapshot(self, monitored: MonitoredDomain):
        """Take initial snapshot of DNS records"""
        if monitored.monitor_dmarc:
            record = self._get_txt_record(f"_dmarc.{monitored.domain}")
            monitored.last_dmarc_hash = self._hash_value(record) if record else None

        if monitored.monitor_spf:
            record = self._get_spf_record(monitored.domain)
            monitored.last_spf_hash = self._hash_value(record) if record else None

        if monitored.monitor_mx:
            records = self._get_mx_records(monitored.domain)
            record_str = ",".join(sorted(records)) if records else None
            monitored.last_mx_hash = self._hash_value(record_str) if record_str else None

        if monitored.monitor_dkim:
            selectors = (
                [s.strip() for s in monitored.dkim_selectors.split(",") if s.strip()]
                if monitored.dkim_selectors
                else self.DEFAULT_DKIM_SELECTORS
            )
            dkim_parts = []
            for selector in selectors:
                record = self._get_txt_record(f"{selector}._domainkey.{monitored.domain}")
                if record:
                    dkim_parts.append(f"{selector}={record}")
            combined = ";".join(sorted(dkim_parts)) if dkim_parts else None
            monitored.last_dkim_hash = self._hash_value(combined) if combined else None

        self.db.commit()

    def _log_change(
        self,
        domain: str,
        record_type: RecordType,
        old_hash: Optional[str],
        new_hash: Optional[str],
        old_value: Optional[str],
        new_value: Optional[str],
    ) -> DNSChange:
        """Log a DNS change"""
        if old_hash is None and new_hash is not None:
            change_type = ChangeType.ADDED
        elif old_hash is not None and new_hash is None:
            change_type = ChangeType.REMOVED
        else:
            change_type = ChangeType.MODIFIED

        log = DNSChangeLog(
            domain=domain,
            record_type=record_type.value,
            change_type=change_type.value,
            old_value=old_value,
            new_value=new_value,
        )

        self.db.add(log)
        self.db.commit()

        logger.info(f"DNS change detected: {domain} {record_type.value} {change_type.value}")

        return DNSChange(
            domain=domain,
            record_type=record_type.value,
            change_type=change_type,
            old_value=old_value,
            new_value=new_value,
            detected_at=datetime.utcnow(),
        )

    def _get_stored_value(self, domain: str, record_type: str) -> Optional[str]:
        """Get last stored value for a record"""
        last_log = self.db.query(DNSChangeLog).filter(
            DNSChangeLog.domain == domain,
            DNSChangeLog.record_type == record_type
        ).order_by(DNSChangeLog.detected_at.desc()).first()

        return last_log.new_value if last_log else None

    # ==================== DNS Lookups ====================

    def _get_txt_record(self, domain: str) -> Optional[str]:
        """Get TXT record"""
        try:
            answers = self.resolver.resolve(domain, 'TXT')
            for rdata in answers:
                return rdata.to_text().strip('"')
        except Exception:
            logger.debug("Failed to resolve TXT record for %s", domain)
        return None

    def _get_spf_record(self, domain: str) -> Optional[str]:
        """Get SPF record"""
        try:
            answers = self.resolver.resolve(domain, 'TXT')
            for rdata in answers:
                txt = rdata.to_text().strip('"')
                if txt.startswith("v=spf1"):
                    return txt
        except Exception:
            logger.debug("Failed to resolve SPF record for %s", domain)
        return None

    def _get_mx_records(self, domain: str) -> List[str]:
        """Get MX records"""
        try:
            answers = self.resolver.resolve(domain, 'MX')
            return [f"{rdata.preference} {rdata.exchange}" for rdata in answers]
        except Exception:
            logger.debug("Failed to resolve MX records for %s", domain)
        return []

    def _hash_value(self, value: str) -> str:
        """Hash a value for comparison"""
        return hashlib.sha256(value.encode()).hexdigest()

    # ==================== Change History ====================

    def get_changes(
        self,
        domain: Optional[str] = None,
        record_type: Optional[str] = None,
        days: int = 30,
        limit: int = 100,
    ) -> List[DNSChangeLog]:
        """Get change history"""
        since = datetime.utcnow() - timedelta(days=days)
        query = self.db.query(DNSChangeLog).filter(
            DNSChangeLog.detected_at >= since
        )

        if domain:
            query = query.filter(DNSChangeLog.domain == domain)
        if record_type:
            query = query.filter(DNSChangeLog.record_type == record_type)

        return query.order_by(DNSChangeLog.detected_at.desc()).limit(limit).all()

    def acknowledge_change(self, change_id: uuid.UUID) -> bool:
        """Acknowledge a change"""
        change = self.db.query(DNSChangeLog).filter(
            DNSChangeLog.id == change_id
        ).first()

        if change:
            change.acknowledged = True
            change.acknowledged_at = datetime.utcnow()
            self.db.commit()
            return True
        return False
