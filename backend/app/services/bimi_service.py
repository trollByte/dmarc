"""
BIMI (Brand Indicators for Message Identification) Service.

Validates and manages BIMI records for displaying brand logos in email clients.

BIMI requirements:
- DMARC policy must be at enforcement (p=quarantine or p=reject)
- Logo must be in SVG Tiny Portable/Secure (SVG P/S) format
- Optional VMC (Verified Mark Certificate) for broader support
"""

import dns.resolver
import httpx
import logging
import hashlib
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
from io import BytesIO

from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base
import uuid

logger = logging.getLogger(__name__)


class BIMIStatus(str, Enum):
    """BIMI validation status"""
    VALID = "valid"
    INVALID = "invalid"
    PARTIAL = "partial"  # Valid but missing VMC
    MISSING = "missing"


class LogoFormat(str, Enum):
    """Logo format types"""
    SVG_PS = "svg_ps"  # SVG Tiny Portable/Secure
    SVG = "svg"  # Regular SVG (not compliant)
    OTHER = "other"


@dataclass
class BIMIRecord:
    """Parsed BIMI DNS record"""
    version: str
    logo_url: Optional[str]
    authority_url: Optional[str]  # VMC URL
    raw: str


@dataclass
class LogoValidation:
    """Logo validation result"""
    url: str
    accessible: bool
    content_type: Optional[str]
    format: LogoFormat
    size_bytes: int
    is_valid: bool
    issues: List[str]


@dataclass
class VMCValidation:
    """VMC (Verified Mark Certificate) validation result"""
    url: str
    accessible: bool
    has_certificate: bool
    is_valid: bool
    issuer: Optional[str]
    expires_at: Optional[datetime]
    issues: List[str]


@dataclass
class BIMICheck:
    """Complete BIMI validation result"""
    domain: str
    status: BIMIStatus
    has_record: bool
    record: Optional[BIMIRecord]
    dmarc_compliant: bool
    dmarc_policy: Optional[str]
    logo_validation: Optional[LogoValidation]
    vmc_validation: Optional[VMCValidation]
    issues: List[str]
    warnings: List[str]
    checked_at: datetime


class BIMIDomain(Base):
    """Tracked BIMI domains"""
    __tablename__ = "bimi_domains"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain = Column(String(255), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # BIMI record info
    has_bimi_record = Column(Boolean, default=False, nullable=False)
    logo_url = Column(Text, nullable=True)
    authority_url = Column(Text, nullable=True)

    # Validation status
    last_status = Column(String(20), nullable=True)
    dmarc_compliant = Column(Boolean, default=False, nullable=False)
    logo_valid = Column(Boolean, default=False, nullable=False)
    vmc_valid = Column(Boolean, nullable=True)

    # Cached logo
    logo_hash = Column(String(64), nullable=True)
    logo_cached_at = Column(DateTime, nullable=True)

    # Check history
    last_checked_at = Column(DateTime, nullable=True)
    last_change_at = Column(DateTime, nullable=True)
    consecutive_failures = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<BIMIDomain(domain={self.domain})>"


class BIMIChangeLog(Base):
    """Log of BIMI changes"""
    __tablename__ = "bimi_change_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain = Column(String(255), nullable=False, index=True)
    change_type = Column(String(50), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    details = Column(JSONB, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<BIMIChangeLog(domain={self.domain}, change={self.change_type})>"


class BIMIService:
    """Service for BIMI validation and monitoring"""

    BIMI_SELECTOR = "default"  # Most common selector
    BIMI_RECORD_PREFIX = "_bimi"

    def __init__(self, db: Session):
        self.db = db
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = 5
        self.resolver.lifetime = 10

    # ==================== Domain Management ====================

    def add_domain(self, domain: str) -> BIMIDomain:
        """Add a domain to BIMI monitoring"""
        existing = self.db.query(BIMIDomain).filter(
            BIMIDomain.domain == domain
        ).first()

        if existing:
            existing.is_active = True
            self.db.commit()
            return existing

        bimi = BIMIDomain(domain=domain)
        self.db.add(bimi)
        self.db.commit()
        self.db.refresh(bimi)

        # Initial check
        self._check_and_update(bimi)

        return bimi

    def remove_domain(self, domain: str) -> bool:
        """Remove domain from monitoring"""
        bimi = self.db.query(BIMIDomain).filter(
            BIMIDomain.domain == domain
        ).first()

        if bimi:
            bimi.is_active = False
            self.db.commit()
            return True
        return False

    def get_domains(self, active_only: bool = True) -> List[BIMIDomain]:
        """Get monitored domains"""
        query = self.db.query(BIMIDomain)
        if active_only:
            query = query.filter(BIMIDomain.is_active == True)
        return query.order_by(BIMIDomain.domain).all()

    # ==================== Validation ====================

    def check_domain(self, domain: str, selector: str = "default") -> BIMICheck:
        """Check BIMI configuration for a domain"""
        return self._perform_check(domain, selector)

    def check_all_domains(self) -> Dict[str, BIMICheck]:
        """Check all monitored domains"""
        domains = self.get_domains(active_only=True)
        results = {}

        for bimi in domains:
            check = self._check_and_update(bimi)
            results[bimi.domain] = check

        return results

    def _check_and_update(self, bimi: BIMIDomain) -> BIMICheck:
        """Check domain and update stored state"""
        check = self._perform_check(bimi.domain)

        # Detect changes
        self._detect_changes(bimi, check)

        # Update stored state
        bimi.has_bimi_record = check.has_record
        bimi.last_status = check.status.value
        bimi.dmarc_compliant = check.dmarc_compliant
        bimi.last_checked_at = check.checked_at

        if check.record:
            bimi.logo_url = check.record.logo_url
            bimi.authority_url = check.record.authority_url

        if check.logo_validation:
            bimi.logo_valid = check.logo_validation.is_valid
            if check.logo_validation.is_valid:
                bimi.logo_hash = hashlib.sha256(
                    check.logo_validation.url.encode()
                ).hexdigest()
                bimi.logo_cached_at = datetime.utcnow()

        if check.vmc_validation:
            bimi.vmc_valid = check.vmc_validation.is_valid

        if check.status == BIMIStatus.VALID:
            bimi.consecutive_failures = 0
        else:
            bimi.consecutive_failures += 1

        self.db.commit()
        return check

    def _perform_check(self, domain: str, selector: str = "default") -> BIMICheck:
        """Perform complete BIMI check"""
        issues = []
        warnings = []
        record = None
        logo_validation = None
        vmc_validation = None

        # Check DMARC compliance first
        dmarc_policy, dmarc_compliant = self._check_dmarc(domain)
        if not dmarc_compliant:
            issues.append(f"DMARC policy must be 'quarantine' or 'reject' (current: {dmarc_policy or 'none'})")

        # Get BIMI record
        record = self._get_bimi_record(domain, selector)
        has_record = record is not None

        if not has_record:
            return BIMICheck(
                domain=domain,
                status=BIMIStatus.MISSING,
                has_record=False,
                record=None,
                dmarc_compliant=dmarc_compliant,
                dmarc_policy=dmarc_policy,
                logo_validation=None,
                vmc_validation=None,
                issues=["No BIMI record found"],
                warnings=warnings,
                checked_at=datetime.utcnow(),
            )

        # Validate logo
        if record.logo_url:
            logo_validation = self._validate_logo(record.logo_url)
            if not logo_validation.is_valid:
                issues.extend(logo_validation.issues)
        else:
            issues.append("No logo URL in BIMI record")

        # Validate VMC (optional but recommended)
        if record.authority_url:
            vmc_validation = self._validate_vmc(record.authority_url)
            if not vmc_validation.is_valid:
                warnings.extend(vmc_validation.issues)
        else:
            warnings.append("No VMC (Verified Mark Certificate) - logo may not display in all clients")

        # Determine status
        if issues:
            status = BIMIStatus.INVALID
        elif not vmc_validation or not vmc_validation.is_valid:
            status = BIMIStatus.PARTIAL
        else:
            status = BIMIStatus.VALID

        return BIMICheck(
            domain=domain,
            status=status,
            has_record=has_record,
            record=record,
            dmarc_compliant=dmarc_compliant,
            dmarc_policy=dmarc_policy,
            logo_validation=logo_validation,
            vmc_validation=vmc_validation,
            issues=issues,
            warnings=warnings,
            checked_at=datetime.utcnow(),
        )

    def _get_bimi_record(self, domain: str, selector: str = "default") -> Optional[BIMIRecord]:
        """Get BIMI DNS TXT record"""
        try:
            record_name = f"{selector}.{self.BIMI_RECORD_PREFIX}.{domain}"
            answers = self.resolver.resolve(record_name, 'TXT')

            for rdata in answers:
                txt = rdata.to_text().strip('"')

                if "v=BIMI1" in txt:
                    # Parse record
                    parts = {}
                    for item in txt.split(";"):
                        item = item.strip()
                        if "=" in item:
                            key, value = item.split("=", 1)
                            parts[key.strip().lower()] = value.strip()

                    return BIMIRecord(
                        version=parts.get("v", "BIMI1"),
                        logo_url=parts.get("l"),
                        authority_url=parts.get("a"),
                        raw=txt,
                    )
        except Exception as e:
            logger.debug(f"Failed to get BIMI record for {domain}: {e}")
        return None

    def _check_dmarc(self, domain: str) -> tuple[Optional[str], bool]:
        """Check if DMARC policy is compliant for BIMI"""
        try:
            answers = self.resolver.resolve(f"_dmarc.{domain}", 'TXT')

            for rdata in answers:
                txt = rdata.to_text().strip('"')

                if "v=DMARC1" in txt:
                    # Extract policy
                    match = re.search(r'\bp=(\w+)', txt)
                    if match:
                        policy = match.group(1).lower()
                        # BIMI requires quarantine or reject
                        compliant = policy in ["quarantine", "reject"]
                        return policy, compliant

        except Exception as e:
            logger.debug(f"Failed to get DMARC for {domain}: {e}")

        return None, False

    def _validate_logo(self, url: str) -> LogoValidation:
        """Validate BIMI logo"""
        issues = []
        accessible = False
        content_type = None
        format_type = LogoFormat.OTHER
        size_bytes = 0

        try:
            with httpx.Client(timeout=10, follow_redirects=True) as client:
                response = client.get(url)

                if response.status_code == 200:
                    accessible = True
                    content_type = response.headers.get("content-type", "")
                    size_bytes = len(response.content)

                    # Check content type
                    if "svg" in content_type.lower():
                        format_type = LogoFormat.SVG

                        # Check for SVG P/S requirements
                        content = response.text
                        if 'baseProfile="tiny-ps"' in content.lower():
                            format_type = LogoFormat.SVG_PS
                        else:
                            issues.append("Logo must be SVG Tiny Portable/Secure (SVG P/S)")

                        # Check for forbidden elements
                        forbidden = ["<script", "<foreignObject", "javascript:"]
                        for f in forbidden:
                            if f.lower() in content.lower():
                                issues.append(f"Logo contains forbidden element: {f}")
                    else:
                        issues.append(f"Logo must be SVG format (got: {content_type})")

                    # Size check (32KB recommended max)
                    if size_bytes > 32 * 1024:
                        issues.append(f"Logo exceeds recommended 32KB limit ({size_bytes} bytes)")

                else:
                    issues.append(f"Failed to fetch logo: HTTP {response.status_code}")

        except Exception as e:
            issues.append(f"Failed to validate logo: {str(e)}")

        return LogoValidation(
            url=url,
            accessible=accessible,
            content_type=content_type,
            format=format_type,
            size_bytes=size_bytes,
            is_valid=accessible and format_type == LogoFormat.SVG_PS and len(issues) == 0,
            issues=issues,
        )

    def _validate_vmc(self, url: str) -> VMCValidation:
        """Validate VMC (Verified Mark Certificate)"""
        issues = []
        accessible = False
        has_cert = False
        is_valid = False
        issuer = None
        expires_at = None

        try:
            with httpx.Client(timeout=10, follow_redirects=True) as client:
                response = client.get(url)

                if response.status_code == 200:
                    accessible = True
                    content = response.text

                    # Basic PEM certificate check
                    if "-----BEGIN CERTIFICATE-----" in content:
                        has_cert = True

                        # Full validation would require cryptography library
                        # For now, just check basic structure
                        if "-----END CERTIFICATE-----" in content:
                            is_valid = True
                            issuer = "Certificate found (detailed validation not performed)"
                        else:
                            issues.append("Malformed certificate")
                    else:
                        issues.append("No valid certificate found at VMC URL")
                else:
                    issues.append(f"Failed to fetch VMC: HTTP {response.status_code}")

        except Exception as e:
            issues.append(f"Failed to validate VMC: {str(e)}")

        return VMCValidation(
            url=url,
            accessible=accessible,
            has_certificate=has_cert,
            is_valid=is_valid,
            issuer=issuer,
            expires_at=expires_at,
            issues=issues,
        )

    def _detect_changes(self, bimi: BIMIDomain, check: BIMICheck):
        """Detect and log changes"""
        changes = []

        # Record added/removed
        if not bimi.has_bimi_record and check.has_record:
            changes.append({"type": "record_added", "old": None, "new": "BIMI record added"})
        elif bimi.has_bimi_record and not check.has_record:
            changes.append({"type": "record_removed", "old": "BIMI record", "new": None})

        # Logo URL changed
        if check.record and bimi.logo_url != check.record.logo_url:
            changes.append({"type": "logo_changed", "old": bimi.logo_url, "new": check.record.logo_url})

        # VMC URL changed
        if check.record and bimi.authority_url != check.record.authority_url:
            changes.append({"type": "vmc_changed", "old": bimi.authority_url, "new": check.record.authority_url})

        # Status changed
        if bimi.last_status and bimi.last_status != check.status.value:
            changes.append({"type": "status_changed", "old": bimi.last_status, "new": check.status.value})

        for change in changes:
            log = BIMIChangeLog(
                domain=bimi.domain,
                change_type=change["type"],
                old_value=str(change["old"]) if change["old"] else None,
                new_value=str(change["new"]) if change["new"] else None,
                details=change,
            )
            self.db.add(log)
            bimi.last_change_at = datetime.utcnow()

    # ==================== History ====================

    def get_changes(
        self,
        domain: Optional[str] = None,
        days: int = 30,
        limit: int = 100,
    ) -> List[BIMIChangeLog]:
        """Get BIMI change history"""
        since = datetime.utcnow() - timedelta(days=days)
        query = self.db.query(BIMIChangeLog).filter(
            BIMIChangeLog.detected_at >= since
        )

        if domain:
            query = query.filter(BIMIChangeLog.domain == domain)

        return query.order_by(BIMIChangeLog.detected_at.desc()).limit(limit).all()

    # ==================== Record Generation ====================

    def generate_bimi_record(
        self,
        domain: str,
        logo_url: str,
        authority_url: Optional[str] = None,
        selector: str = "default",
    ) -> Dict[str, str]:
        """Generate BIMI DNS record"""
        parts = [f"v=BIMI1", f"l={logo_url}"]
        if authority_url:
            parts.append(f"a={authority_url}")

        record_value = "; ".join(parts)

        return {
            "domain": domain,
            "record_name": f"{selector}._bimi.{domain}",
            "record_type": "TXT",
            "record_value": record_value,
            "ttl": 3600,
        }

    def get_recommendations(self, check: BIMICheck) -> List[str]:
        """Get recommendations based on check results"""
        recs = []

        if not check.dmarc_compliant:
            recs.append("Update DMARC policy to 'quarantine' or 'reject' for BIMI support")

        if not check.has_record:
            recs.append("Add BIMI DNS record: default._bimi.domain TXT \"v=BIMI1; l=https://...logo.svg\"")

        if check.logo_validation and not check.logo_validation.is_valid:
            if check.logo_validation.format != LogoFormat.SVG_PS:
                recs.append("Convert logo to SVG Tiny Portable/Secure (SVG P/S) format")
            recs.append("Ensure logo is hosted on HTTPS with proper content-type")

        if not check.vmc_validation or not check.vmc_validation.is_valid:
            recs.append("Obtain VMC (Verified Mark Certificate) for broader email client support")
            recs.append("VMC providers include DigiCert and Entrust")

        return recs
