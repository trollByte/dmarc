"""
VirusTotal Integration Service.

Provides threat intelligence lookups for:
- IP address reputation
- Domain reputation
- URL scanning
"""

import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Integer, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base
from app.config import get_settings
import uuid

settings = get_settings()
logger = logging.getLogger(__name__)


class ThreatCategory(str, Enum):
    """VirusTotal threat categories"""
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"
    UNKNOWN = "unknown"


@dataclass
class VTIPReport:
    """VirusTotal IP address report"""
    ip_address: str
    malicious_count: int
    suspicious_count: int
    harmless_count: int
    undetected_count: int
    category: ThreatCategory
    country: Optional[str]
    as_owner: Optional[str]
    last_analysis_date: Optional[datetime]
    tags: List[str]
    raw_data: Dict[str, Any]


@dataclass
class VTDomainReport:
    """VirusTotal domain report"""
    domain: str
    malicious_count: int
    suspicious_count: int
    harmless_count: int
    category: ThreatCategory
    registrar: Optional[str]
    creation_date: Optional[datetime]
    last_analysis_date: Optional[datetime]
    reputation: int
    categories: Dict[str, str]
    raw_data: Dict[str, Any]


class VTCache(Base):
    """Cache for VirusTotal lookups"""
    __tablename__ = "virustotal_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lookup_type = Column(String(20), nullable=False, index=True)  # ip, domain, url
    lookup_value = Column(String(255), nullable=False, index=True)
    lookup_hash = Column(String(64), unique=True, nullable=False, index=True)

    # Results
    category = Column(String(20), nullable=False)
    malicious_count = Column(Integer, default=0, nullable=False)
    suspicious_count = Column(Integer, default=0, nullable=False)
    reputation_score = Column(Integer, nullable=True)
    result_data = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)

    def __repr__(self):
        return f"<VTCache({self.lookup_type}={self.lookup_value}, category={self.category})>"


class VirusTotalService:
    """Service for VirusTotal threat intelligence"""

    API_BASE = "https://www.virustotal.com/api/v3"
    CACHE_TTL_HOURS = 24  # Cache results for 24 hours

    def __init__(self, db: Session):
        self.db = db
        self.api_key = getattr(settings, 'virustotal_api_key', '')
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"x-apikey": self.api_key} if self.api_key else {}
        )

    @property
    def is_configured(self) -> bool:
        """Check if API key is configured"""
        return bool(self.api_key)

    async def lookup_ip(self, ip_address: str, use_cache: bool = True) -> Optional[VTIPReport]:
        """
        Lookup IP address reputation.

        Args:
            ip_address: IP address to check
            use_cache: Whether to use cached results

        Returns:
            VTIPReport or None if lookup fails
        """
        if not self.is_configured:
            logger.warning("VirusTotal API key not configured")
            return None

        # Check cache
        if use_cache:
            cached = self._get_cached("ip", ip_address)
            if cached:
                return self._cache_to_ip_report(cached)

        try:
            response = await self.client.get(f"{self.API_BASE}/ip_addresses/{ip_address}")

            if response.status_code == 200:
                data = response.json().get("data", {})
                report = self._parse_ip_response(ip_address, data)

                # Cache result
                self._cache_result("ip", ip_address, report)

                return report

            elif response.status_code == 404:
                # IP not found - cache as unknown
                return VTIPReport(
                    ip_address=ip_address,
                    malicious_count=0,
                    suspicious_count=0,
                    harmless_count=0,
                    undetected_count=0,
                    category=ThreatCategory.UNKNOWN,
                    country=None,
                    as_owner=None,
                    last_analysis_date=None,
                    tags=[],
                    raw_data={},
                )

            else:
                logger.error(f"VirusTotal IP lookup failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"VirusTotal IP lookup error: {e}")
            return None

    async def lookup_domain(self, domain: str, use_cache: bool = True) -> Optional[VTDomainReport]:
        """
        Lookup domain reputation.

        Args:
            domain: Domain to check
            use_cache: Whether to use cached results

        Returns:
            VTDomainReport or None if lookup fails
        """
        if not self.is_configured:
            logger.warning("VirusTotal API key not configured")
            return None

        # Check cache
        if use_cache:
            cached = self._get_cached("domain", domain)
            if cached:
                return self._cache_to_domain_report(cached)

        try:
            response = await self.client.get(f"{self.API_BASE}/domains/{domain}")

            if response.status_code == 200:
                data = response.json().get("data", {})
                report = self._parse_domain_response(domain, data)

                # Cache result
                self._cache_result("domain", domain, report)

                return report

            elif response.status_code == 404:
                return VTDomainReport(
                    domain=domain,
                    malicious_count=0,
                    suspicious_count=0,
                    harmless_count=0,
                    category=ThreatCategory.UNKNOWN,
                    registrar=None,
                    creation_date=None,
                    last_analysis_date=None,
                    reputation=0,
                    categories={},
                    raw_data={},
                )

            else:
                logger.error(f"VirusTotal domain lookup failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"VirusTotal domain lookup error: {e}")
            return None

    def _parse_ip_response(self, ip_address: str, data: Dict) -> VTIPReport:
        """Parse VirusTotal IP response"""
        attrs = data.get("attributes", {})
        stats = attrs.get("last_analysis_stats", {})

        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)

        # Determine category
        if malicious > 0:
            category = ThreatCategory.MALICIOUS
        elif suspicious > 0:
            category = ThreatCategory.SUSPICIOUS
        elif stats.get("harmless", 0) > 0:
            category = ThreatCategory.CLEAN
        else:
            category = ThreatCategory.UNKNOWN

        return VTIPReport(
            ip_address=ip_address,
            malicious_count=malicious,
            suspicious_count=suspicious,
            harmless_count=stats.get("harmless", 0),
            undetected_count=stats.get("undetected", 0),
            category=category,
            country=attrs.get("country"),
            as_owner=attrs.get("as_owner"),
            last_analysis_date=datetime.fromtimestamp(attrs["last_analysis_date"]) if attrs.get("last_analysis_date") else None,
            tags=attrs.get("tags", []),
            raw_data=attrs,
        )

    def _parse_domain_response(self, domain: str, data: Dict) -> VTDomainReport:
        """Parse VirusTotal domain response"""
        attrs = data.get("attributes", {})
        stats = attrs.get("last_analysis_stats", {})

        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)

        if malicious > 0:
            category = ThreatCategory.MALICIOUS
        elif suspicious > 0:
            category = ThreatCategory.SUSPICIOUS
        elif stats.get("harmless", 0) > 0:
            category = ThreatCategory.CLEAN
        else:
            category = ThreatCategory.UNKNOWN

        return VTDomainReport(
            domain=domain,
            malicious_count=malicious,
            suspicious_count=suspicious,
            harmless_count=stats.get("harmless", 0),
            category=category,
            registrar=attrs.get("registrar"),
            creation_date=datetime.fromtimestamp(attrs["creation_date"]) if attrs.get("creation_date") else None,
            last_analysis_date=datetime.fromtimestamp(attrs["last_analysis_date"]) if attrs.get("last_analysis_date") else None,
            reputation=attrs.get("reputation", 0),
            categories=attrs.get("categories", {}),
            raw_data=attrs,
        )

    def _get_cached(self, lookup_type: str, value: str) -> Optional[VTCache]:
        """Get cached lookup result"""
        lookup_hash = hashlib.sha256(f"{lookup_type}:{value}".encode()).hexdigest()

        return self.db.query(VTCache).filter(
            VTCache.lookup_hash == lookup_hash,
            VTCache.expires_at > datetime.utcnow()
        ).first()

    def _cache_result(self, lookup_type: str, value: str, report):
        """Cache lookup result"""
        lookup_hash = hashlib.sha256(f"{lookup_type}:{value}".encode()).hexdigest()

        # Delete existing cache entry
        self.db.query(VTCache).filter(VTCache.lookup_hash == lookup_hash).delete()

        cache = VTCache(
            lookup_type=lookup_type,
            lookup_value=value,
            lookup_hash=lookup_hash,
            category=report.category.value,
            malicious_count=report.malicious_count,
            suspicious_count=report.suspicious_count,
            reputation_score=getattr(report, 'reputation', None),
            result_data=report.raw_data,
            expires_at=datetime.utcnow() + timedelta(hours=self.CACHE_TTL_HOURS),
        )

        self.db.add(cache)
        self.db.commit()

    def _cache_to_ip_report(self, cache: VTCache) -> VTIPReport:
        """Convert cache to IP report"""
        return VTIPReport(
            ip_address=cache.lookup_value,
            malicious_count=cache.malicious_count,
            suspicious_count=cache.suspicious_count,
            harmless_count=cache.result_data.get("last_analysis_stats", {}).get("harmless", 0) if cache.result_data else 0,
            undetected_count=cache.result_data.get("last_analysis_stats", {}).get("undetected", 0) if cache.result_data else 0,
            category=ThreatCategory(cache.category),
            country=cache.result_data.get("country") if cache.result_data else None,
            as_owner=cache.result_data.get("as_owner") if cache.result_data else None,
            last_analysis_date=None,
            tags=cache.result_data.get("tags", []) if cache.result_data else [],
            raw_data=cache.result_data or {},
        )

    def _cache_to_domain_report(self, cache: VTCache) -> VTDomainReport:
        """Convert cache to domain report"""
        return VTDomainReport(
            domain=cache.lookup_value,
            malicious_count=cache.malicious_count,
            suspicious_count=cache.suspicious_count,
            harmless_count=cache.result_data.get("last_analysis_stats", {}).get("harmless", 0) if cache.result_data else 0,
            category=ThreatCategory(cache.category),
            registrar=cache.result_data.get("registrar") if cache.result_data else None,
            creation_date=None,
            last_analysis_date=None,
            reputation=cache.reputation_score or 0,
            categories=cache.result_data.get("categories", {}) if cache.result_data else {},
            raw_data=cache.result_data or {},
        )

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        from sqlalchemy import func

        total = self.db.query(func.count(VTCache.id)).scalar() or 0
        expired = self.db.query(func.count(VTCache.id)).filter(
            VTCache.expires_at <= datetime.utcnow()
        ).scalar() or 0

        by_type = self.db.query(
            VTCache.lookup_type,
            func.count(VTCache.id)
        ).group_by(VTCache.lookup_type).all()

        by_category = self.db.query(
            VTCache.category,
            func.count(VTCache.id)
        ).group_by(VTCache.category).all()

        return {
            "total_cached": total,
            "expired": expired,
            "active": total - expired,
            "by_type": {t: c for t, c in by_type},
            "by_category": {c: n for c, n in by_category},
            "api_configured": self.is_configured,
        }

    def cleanup_expired(self) -> int:
        """Clean up expired cache entries"""
        deleted = self.db.query(VTCache).filter(
            VTCache.expires_at < datetime.utcnow()
        ).delete()
        self.db.commit()
        return deleted
