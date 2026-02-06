"""
API routes for Threat Intelligence.

Provides IP threat lookups via AbuseIPDB and other sources.
"""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models import User, UserRole
from app.services.threat_intel import ThreatIntelService, ThreatLevel
from app.services.virustotal_service import VirusTotalService
from app.schemas.threat_intel_schemas import (
    ThreatInfoResponse,
    ThreatCheckRequest,
    ThreatBulkCheckRequest,
    ThreatBulkCheckResponse,
    ThreatCacheStatsResponse,
    HighThreatIPResponse,
    EnrichedAnomalyResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/threat-intel", tags=["threat-intel"])


@router.get(
    "/check/{ip_address}",
    response_model=ThreatInfoResponse,
    summary="Check IP threat level"
)
async def check_ip_threat(
    ip_address: str,
    use_cache: bool = Query(default=True, description="Use cached results"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check threat intelligence for a single IP address.

    Uses AbuseIPDB and VirusTotal (if configured) to get:
    - Abuse confidence score (0-100)
    - Number of abuse reports
    - Attack categories
    - ISP and location info
    - Tor exit node detection
    - VirusTotal malicious/suspicious verdicts

    Results are cached for 24 hours.
    """
    service = ThreatIntelService(db)
    result = service.check_ip(ip_address, use_cache=use_cache)

    if not result:
        raise HTTPException(
            status_code=503,
            detail="Threat intelligence service unavailable. Check API key configuration."
        )

    # Supplement with VirusTotal data if configured
    vt_data = None
    vt_service = VirusTotalService(db)
    if vt_service.is_configured:
        try:
            vt_data = await vt_service.lookup_ip(ip_address, use_cache=use_cache)
        except Exception as e:
            logger.warning(f"VirusTotal lookup failed for {ip_address}: {e}")

    source = result.source
    if vt_data:
        source = f"{result.source}+virustotal"
        # Append VT categories to existing categories
        if vt_data.malicious_count > 0:
            if "VirusTotal:malicious" not in result.categories:
                result.categories.append(f"VirusTotal:malicious({vt_data.malicious_count})")
        if vt_data.suspicious_count > 0:
            if "VirusTotal:suspicious" not in result.categories:
                result.categories.append(f"VirusTotal:suspicious({vt_data.suspicious_count})")

    return ThreatInfoResponse(
        ip_address=result.ip_address,
        threat_level=result.threat_level,
        abuse_score=result.abuse_score,
        total_reports=result.total_reports,
        last_reported=result.last_reported,
        is_whitelisted=result.is_whitelisted,
        is_tor=result.is_tor,
        is_public=result.is_public,
        isp=result.isp,
        domain=result.domain,
        country_code=result.country_code,
        usage_type=result.usage_type,
        categories=result.categories,
        cached_at=result.cached_at,
        source=source,
    )


@router.post(
    "/check-bulk",
    response_model=ThreatBulkCheckResponse,
    summary="Check multiple IPs (analyst+)"
)
async def check_ips_bulk(
    request: ThreatBulkCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ANALYST)),
):
    """
    Check threat intelligence for multiple IP addresses.

    **Analyst or Admin only** (to prevent API abuse).

    Note: AbuseIPDB has rate limits. Cached results are returned
    immediately; uncached IPs are checked against the API.

    Maximum 100 IPs per request.
    """
    service = ThreatIntelService(db)
    results = service.check_ips_bulk(
        request.ip_addresses,
        use_cache=request.use_cache
    )

    # Build response
    response_results = {}
    summary = {level.value: 0 for level in ThreatLevel}
    checked = 0

    for ip, info in results.items():
        if info:
            checked += 1
            summary[info.threat_level.value] += 1
            response_results[ip] = ThreatInfoResponse(
                ip_address=info.ip_address,
                threat_level=info.threat_level,
                abuse_score=info.abuse_score,
                total_reports=info.total_reports,
                last_reported=info.last_reported,
                is_whitelisted=info.is_whitelisted,
                is_tor=info.is_tor,
                is_public=info.is_public,
                isp=info.isp,
                domain=info.domain,
                country_code=info.country_code,
                usage_type=info.usage_type,
                categories=info.categories,
                cached_at=info.cached_at,
                source=info.source,
            )
        else:
            response_results[ip] = None

    return ThreatBulkCheckResponse(
        total=len(request.ip_addresses),
        checked=checked,
        results=response_results,
        summary=summary,
    )


@router.get(
    "/cache/stats",
    response_model=ThreatCacheStatsResponse,
    summary="Get cache statistics"
)
async def get_cache_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get threat intelligence cache statistics.

    Shows:
    - Total and active cache entries
    - Breakdown by threat level
    - Whether API is configured
    """
    service = ThreatIntelService(db)
    stats = service.get_cache_stats()
    return ThreatCacheStatsResponse(**stats)


@router.get(
    "/high-threat",
    response_model=List[HighThreatIPResponse],
    summary="Get high-threat IPs from cache"
)
async def get_high_threat_ips(
    min_score: int = Query(default=50, ge=0, le=100, description="Minimum abuse score"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all cached IPs with high threat scores.

    Returns IPs that have been checked and have abuse scores
    above the specified threshold.
    """
    service = ThreatIntelService(db)
    high_threat = service.get_high_threat_ips(min_score)[:limit]

    return [
        HighThreatIPResponse(
            ip_address=ip.ip_address,
            threat_level=ip.threat_level,
            abuse_score=ip.abuse_score,
            total_reports=ip.total_reports,
            last_reported=ip.last_reported,
            isp=ip.isp,
            country_code=ip.country_code,
            categories=ip.categories or [],
            created_at=ip.created_at,
        )
        for ip in high_threat
    ]


@router.post(
    "/cache/purge",
    summary="Purge expired cache (admin only)"
)
async def purge_cache(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Purge expired threat intelligence cache entries.

    **Admin only**.
    """
    service = ThreatIntelService(db)
    purged = service.purge_expired_cache()

    return {
        "status": "success",
        "purged_entries": purged,
    }


@router.get(
    "/enrich-anomalies",
    response_model=List[EnrichedAnomalyResponse],
    summary="Get anomalies enriched with threat intel"
)
async def get_enriched_anomalies(
    days: int = Query(default=7, ge=1, le=30, description="Days of data"),
    limit: int = Query(default=20, ge=1, le=100, description="Max results"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get recent ML anomalies enriched with threat intelligence.

    Combines:
    - ML anomaly scores
    - AbuseIPDB threat data
    - Combined risk score

    This helps prioritize which anomalies to investigate first.
    """
    from app.services.ml_analytics import MLAnalyticsService

    ml_service = MLAnalyticsService(db)
    threat_service = ThreatIntelService(db)

    # Get deployed model
    deployed_model = ml_service.get_deployed_model()
    if not deployed_model:
        raise HTTPException(
            status_code=400,
            detail="No deployed ML model. Train and deploy a model first."
        )

    # Detect anomalies
    anomalies = ml_service.detect_anomalies(days=days, threshold=-0.5)

    # Enrich with threat intel
    enriched = []
    for anomaly in sorted(anomalies, key=lambda x: x["anomaly_score"])[:limit]:
        ip = anomaly["ip_address"]
        threat_info = threat_service.check_ip(ip, use_cache=True)

        # Calculate combined risk score
        # Normalize anomaly score (-1 to 0) to (0 to 50)
        anomaly_risk = min(50, abs(anomaly["anomaly_score"]) * 50)

        # Abuse score contributes 0-50
        threat_risk = (threat_info.abuse_score / 2) if threat_info else 0

        combined_score = min(100, anomaly_risk + threat_risk)

        # Identify risk factors
        risk_factors = []
        if anomaly["anomaly_score"] < -0.7:
            risk_factors.append("Highly anomalous behavior")
        if threat_info and threat_info.abuse_score >= 50:
            risk_factors.append(f"High abuse score ({threat_info.abuse_score})")
        if threat_info and threat_info.is_tor:
            risk_factors.append("Tor exit node")
        if threat_info and "Brute-Force" in threat_info.categories:
            risk_factors.append("Known brute-force source")
        if threat_info and "Email Spam" in threat_info.categories:
            risk_factors.append("Known spam source")
        if anomaly["features"]["failure_rate"] > 50:
            risk_factors.append(f"High failure rate ({anomaly['features']['failure_rate']:.0f}%)")

        threat_response = None
        if threat_info and threat_info.source != "none":
            threat_response = ThreatInfoResponse(
                ip_address=threat_info.ip_address,
                threat_level=threat_info.threat_level,
                abuse_score=threat_info.abuse_score,
                total_reports=threat_info.total_reports,
                last_reported=threat_info.last_reported,
                is_whitelisted=threat_info.is_whitelisted,
                is_tor=threat_info.is_tor,
                is_public=threat_info.is_public,
                isp=threat_info.isp,
                domain=threat_info.domain,
                country_code=threat_info.country_code,
                usage_type=threat_info.usage_type,
                categories=threat_info.categories,
                cached_at=threat_info.cached_at,
                source=threat_info.source,
            )

        enriched.append(EnrichedAnomalyResponse(
            ip_address=ip,
            anomaly_score=anomaly["anomaly_score"],
            features=anomaly["features"],
            threat_info=threat_response,
            combined_risk_score=combined_score,
            risk_factors=risk_factors,
        ))

    # Sort by combined risk score
    enriched.sort(key=lambda x: x.combined_risk_score, reverse=True)

    return enriched
