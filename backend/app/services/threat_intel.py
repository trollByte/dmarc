"""
Threat Intelligence Service

Integrates with external threat intelligence sources to enrich IP data:
- AbuseIPDB: IP reputation and abuse reports
- Caching to minimize API calls

Future integrations:
- VirusTotal
- Shodan
- GreyNoise
"""

import logging
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.database import Base
from app.config import get_settings

logger = logging.getLogger(__name__)


class ThreatLevel(str, Enum):
    """Threat level classification"""
    CRITICAL = "critical"  # 80-100 abuse score
    HIGH = "high"          # 50-79 abuse score
    MEDIUM = "medium"      # 25-49 abuse score
    LOW = "low"            # 1-24 abuse score
    CLEAN = "clean"        # 0 abuse score
    UNKNOWN = "unknown"    # Not checked


@dataclass
class ThreatInfo:
    """Threat intelligence data for an IP"""
    ip_address: str
    threat_level: ThreatLevel
    abuse_score: int  # 0-100
    total_reports: int
    last_reported: Optional[datetime]
    is_whitelisted: bool
    is_tor: bool
    is_public: bool
    isp: Optional[str]
    domain: Optional[str]
    country_code: Optional[str]
    usage_type: Optional[str]
    categories: List[str]  # Attack categories
    cached_at: datetime
    source: str  # e.g., "abuseipdb"


class ThreatIntelCache(Base):
    """Cache for threat intelligence lookups"""
    __tablename__ = "threat_intel_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ip_address = Column(String(45), unique=True, index=True, nullable=False)
    source = Column(String(50), nullable=False)  # abuseipdb, virustotal, etc.
    threat_level = Column(String(20), nullable=False)
    abuse_score = Column(Integer, default=0)
    total_reports = Column(Integer, default=0)
    last_reported = Column(DateTime, nullable=True)
    is_whitelisted = Column(Integer, default=0)  # SQLite doesn't have boolean
    is_tor = Column(Integer, default=0)
    isp = Column(String(255), nullable=True)
    domain = Column(String(255), nullable=True)
    country_code = Column(String(10), nullable=True)
    usage_type = Column(String(100), nullable=True)
    categories = Column(JSON, default=list)
    raw_response = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


# AbuseIPDB category codes
ABUSEIPDB_CATEGORIES = {
    1: "DNS Compromise",
    2: "DNS Poisoning",
    3: "Fraud Orders",
    4: "DDoS Attack",
    5: "FTP Brute-Force",
    6: "Ping of Death",
    7: "Phishing",
    8: "Fraud VoIP",
    9: "Open Proxy",
    10: "Web Spam",
    11: "Email Spam",
    12: "Blog Spam",
    13: "VPN IP",
    14: "Port Scan",
    15: "Hacking",
    16: "SQL Injection",
    17: "Spoofing",
    18: "Brute-Force",
    19: "Bad Web Bot",
    20: "Exploited Host",
    21: "Web App Attack",
    22: "SSH",
    23: "IoT Targeted",
}


class ThreatIntelService:
    """
    Threat intelligence service with multiple source support.
    """

    CACHE_TTL_HOURS = 24  # Cache entries for 24 hours

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self._abuseipdb_key = getattr(self.settings, 'abuseipdb_api_key', None)

    def _get_cached(self, ip_address: str) -> Optional[ThreatIntelCache]:
        """Get cached threat intel if not expired"""
        cached = self.db.query(ThreatIntelCache).filter(
            ThreatIntelCache.ip_address == ip_address,
            ThreatIntelCache.expires_at > datetime.utcnow()
        ).first()
        return cached

    def _cache_result(
        self,
        ip_address: str,
        source: str,
        data: Dict[str, Any]
    ) -> ThreatIntelCache:
        """Cache threat intel result"""
        # Delete existing cache for this IP
        self.db.query(ThreatIntelCache).filter(
            ThreatIntelCache.ip_address == ip_address
        ).delete()

        cache_entry = ThreatIntelCache(
            ip_address=ip_address,
            source=source,
            threat_level=data.get('threat_level', ThreatLevel.UNKNOWN.value),
            abuse_score=data.get('abuse_score', 0),
            total_reports=data.get('total_reports', 0),
            last_reported=data.get('last_reported'),
            is_whitelisted=1 if data.get('is_whitelisted') else 0,
            is_tor=1 if data.get('is_tor') else 0,
            isp=data.get('isp'),
            domain=data.get('domain'),
            country_code=data.get('country_code'),
            usage_type=data.get('usage_type'),
            categories=data.get('categories', []),
            raw_response=data.get('raw_response', {}),
            expires_at=datetime.utcnow() + timedelta(hours=self.CACHE_TTL_HOURS)
        )

        self.db.add(cache_entry)
        self.db.commit()
        self.db.refresh(cache_entry)

        return cache_entry

    def _score_to_threat_level(self, score: int) -> ThreatLevel:
        """Convert abuse score to threat level"""
        if score >= 80:
            return ThreatLevel.CRITICAL
        elif score >= 50:
            return ThreatLevel.HIGH
        elif score >= 25:
            return ThreatLevel.MEDIUM
        elif score >= 1:
            return ThreatLevel.LOW
        else:
            return ThreatLevel.CLEAN

    def check_ip_abuseipdb(
        self,
        ip_address: str,
        max_age_days: int = 90,
        use_cache: bool = True
    ) -> Optional[ThreatInfo]:
        """
        Check IP against AbuseIPDB.

        Args:
            ip_address: IP address to check
            max_age_days: Only consider reports from last N days
            use_cache: Whether to use cached results

        Returns:
            ThreatInfo object or None if lookup fails
        """
        # Check cache first
        if use_cache:
            cached = self._get_cached(ip_address)
            if cached:
                return ThreatInfo(
                    ip_address=ip_address,
                    threat_level=ThreatLevel(cached.threat_level),
                    abuse_score=cached.abuse_score,
                    total_reports=cached.total_reports,
                    last_reported=cached.last_reported,
                    is_whitelisted=bool(cached.is_whitelisted),
                    is_tor=bool(cached.is_tor),
                    is_public=True,
                    isp=cached.isp,
                    domain=cached.domain,
                    country_code=cached.country_code,
                    usage_type=cached.usage_type,
                    categories=cached.categories or [],
                    cached_at=cached.created_at,
                    source="abuseipdb_cache"
                )

        # Check if API key is configured
        if not self._abuseipdb_key:
            logger.warning("AbuseIPDB API key not configured")
            return None

        # Call AbuseIPDB API
        try:
            url = "https://api.abuseipdb.com/api/v2/check"
            headers = {
                "Key": self._abuseipdb_key,
                "Accept": "application/json"
            }
            params = {
                "ipAddress": ip_address,
                "maxAgeInDays": max_age_days,
                "verbose": True
            }

            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json().get("data", {})

            # Parse categories
            categories = []
            for report in data.get("reports", []):
                for cat_id in report.get("categories", []):
                    cat_name = ABUSEIPDB_CATEGORIES.get(cat_id)
                    if cat_name and cat_name not in categories:
                        categories.append(cat_name)

            abuse_score = data.get("abuseConfidenceScore", 0)
            threat_level = self._score_to_threat_level(abuse_score)

            # Parse last reported date
            last_reported = None
            if data.get("lastReportedAt"):
                try:
                    last_reported = datetime.fromisoformat(
                        data["lastReportedAt"].replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except:
                    pass

            # Cache the result
            cache_data = {
                "threat_level": threat_level.value,
                "abuse_score": abuse_score,
                "total_reports": data.get("totalReports", 0),
                "last_reported": last_reported,
                "is_whitelisted": data.get("isWhitelisted", False),
                "is_tor": data.get("isTor", False),
                "isp": data.get("isp"),
                "domain": data.get("domain"),
                "country_code": data.get("countryCode"),
                "usage_type": data.get("usageType"),
                "categories": categories,
                "raw_response": data,
            }

            self._cache_result(ip_address, "abuseipdb", cache_data)

            return ThreatInfo(
                ip_address=ip_address,
                threat_level=threat_level,
                abuse_score=abuse_score,
                total_reports=data.get("totalReports", 0),
                last_reported=last_reported,
                is_whitelisted=data.get("isWhitelisted", False),
                is_tor=data.get("isTor", False),
                is_public=data.get("isPublic", True),
                isp=data.get("isp"),
                domain=data.get("domain"),
                country_code=data.get("countryCode"),
                usage_type=data.get("usageType"),
                categories=categories,
                cached_at=datetime.utcnow(),
                source="abuseipdb"
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"AbuseIPDB API error for {ip_address}: {e}")
            return None

    def check_ip(
        self,
        ip_address: str,
        use_cache: bool = True
    ) -> Optional[ThreatInfo]:
        """
        Check IP against all configured threat intelligence sources.

        Currently supports:
        - AbuseIPDB

        Args:
            ip_address: IP address to check
            use_cache: Whether to use cached results

        Returns:
            ThreatInfo object or None if lookup fails
        """
        # Try AbuseIPDB first
        result = self.check_ip_abuseipdb(ip_address, use_cache=use_cache)
        if result:
            return result

        # Return unknown if no sources available
        return ThreatInfo(
            ip_address=ip_address,
            threat_level=ThreatLevel.UNKNOWN,
            abuse_score=0,
            total_reports=0,
            last_reported=None,
            is_whitelisted=False,
            is_tor=False,
            is_public=True,
            isp=None,
            domain=None,
            country_code=None,
            usage_type=None,
            categories=[],
            cached_at=datetime.utcnow(),
            source="none"
        )

    def check_ips_bulk(
        self,
        ip_addresses: List[str],
        use_cache: bool = True
    ) -> Dict[str, Optional[ThreatInfo]]:
        """
        Check multiple IPs against threat intelligence sources.

        Note: AbuseIPDB has rate limits, so this checks cached first
        then makes API calls for uncached IPs.

        Args:
            ip_addresses: List of IP addresses
            use_cache: Whether to use cached results

        Returns:
            Dictionary mapping IP -> ThreatInfo
        """
        results = {}

        for ip in ip_addresses:
            results[ip] = self.check_ip(ip, use_cache=use_cache)

        return results

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get threat intel cache statistics"""
        total = self.db.query(ThreatIntelCache).count()
        active = self.db.query(ThreatIntelCache).filter(
            ThreatIntelCache.expires_at > datetime.utcnow()
        ).count()

        # Count by threat level
        threat_counts = {}
        for level in ThreatLevel:
            count = self.db.query(ThreatIntelCache).filter(
                ThreatIntelCache.threat_level == level.value,
                ThreatIntelCache.expires_at > datetime.utcnow()
            ).count()
            threat_counts[level.value] = count

        return {
            "total_entries": total,
            "active_entries": active,
            "expired_entries": total - active,
            "by_threat_level": threat_counts,
            "api_configured": bool(self._abuseipdb_key),
        }

    def purge_expired_cache(self) -> int:
        """Purge expired cache entries"""
        result = self.db.query(ThreatIntelCache).filter(
            ThreatIntelCache.expires_at <= datetime.utcnow()
        ).delete()
        self.db.commit()
        return result

    def get_high_threat_ips(self, min_score: int = 50) -> List[ThreatIntelCache]:
        """Get all cached IPs with high threat scores"""
        return self.db.query(ThreatIntelCache).filter(
            ThreatIntelCache.abuse_score >= min_score,
            ThreatIntelCache.expires_at > datetime.utcnow()
        ).order_by(ThreatIntelCache.abuse_score.desc()).all()
