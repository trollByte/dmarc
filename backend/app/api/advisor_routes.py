"""
API routes for DMARC Policy Advisor.

Provides AI-powered recommendations for:
- Policy upgrades (none → quarantine → reject)
- New sender authorization
- SPF/DKIM alignment improvements
- Domain health scoring
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models import User
from app.services.policy_advisor import PolicyAdvisor
from app.schemas.advisor_schemas import (
    RecommendationResponse,
    DomainHealthResponse,
    DomainStatsResponse,
    FailingSenderResponse,
    OverallHealthResponse,
    RecommendationsListResponse,
    DomainListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/advisor", tags=["advisor"])


# ==================== Health & Overview ====================

@router.get(
    "/health",
    response_model=OverallHealthResponse,
    summary="Get overall DMARC health"
)
async def get_overall_health(
    days: int = Query(default=30, ge=7, le=90, description="Days to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get overall DMARC health summary across all domains.

    Returns:
    - Overall health score (0-100) and grade (A-F)
    - Policy breakdown (how many domains at none/quarantine/reject)
    - Total emails and sources analyzed
    """
    advisor = PolicyAdvisor(db)
    health = advisor.get_overall_health(days)
    return OverallHealthResponse(**health)


@router.get(
    "/health/{domain}",
    response_model=DomainHealthResponse,
    summary="Get domain health score"
)
async def get_domain_health(
    domain: str,
    days: int = Query(default=30, ge=7, le=90, description="Days to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get health score and analysis for a specific domain.

    Returns:
    - Health score (0-100) and grade (A-F)
    - Pass rates for DMARC, SPF, DKIM
    - Current and recommended policy
    - List of issues identified
    """
    advisor = PolicyAdvisor(db)
    health = advisor.get_domain_health_score(domain, days)

    if not health:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for domain: {domain}"
        )

    return DomainHealthResponse(
        domain=health.domain,
        overall_score=health.overall_score,
        pass_rate=health.pass_rate,
        spf_alignment_rate=health.spf_alignment_rate,
        dkim_alignment_rate=health.dkim_alignment_rate,
        current_policy=health.current_policy,
        recommended_policy=health.recommended_policy,
        total_emails=health.total_emails,
        total_sources=health.total_sources,
        issues=health.issues,
        grade=health.grade,
    )


@router.get(
    "/domains",
    response_model=DomainListResponse,
    summary="Get all domains with health scores"
)
async def get_all_domains_health(
    days: int = Query(default=30, ge=7, le=90, description="Days to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get health scores for all domains.

    Returns list of domains sorted by health score (worst first).
    """
    from app.models import DmarcReport

    advisor = PolicyAdvisor(db)

    # Get all domains
    domains = db.query(DmarcReport.domain).distinct().all()
    domains = [d[0] for d in domains]

    health_scores = []
    for domain in domains:
        health = advisor.get_domain_health_score(domain, days)
        if health:
            health_scores.append(DomainHealthResponse(
                domain=health.domain,
                overall_score=health.overall_score,
                pass_rate=health.pass_rate,
                spf_alignment_rate=health.spf_alignment_rate,
                dkim_alignment_rate=health.dkim_alignment_rate,
                current_policy=health.current_policy,
                recommended_policy=health.recommended_policy,
                total_emails=health.total_emails,
                total_sources=health.total_sources,
                issues=health.issues,
                grade=health.grade,
            ))

    # Sort by score (worst first)
    health_scores.sort(key=lambda x: x.overall_score)

    return DomainListResponse(
        total=len(health_scores),
        domains=health_scores,
    )


# ==================== Recommendations ====================

@router.get(
    "/recommendations",
    response_model=RecommendationsListResponse,
    summary="Get all recommendations"
)
async def get_all_recommendations(
    days: int = Query(default=30, ge=7, le=90, description="Days to analyze"),
    limit: int = Query(default=50, ge=1, le=200, description="Max recommendations"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all policy recommendations across all domains.

    Recommendations are sorted by priority (critical first).

    Includes:
    - Policy upgrade recommendations
    - Failing sender alerts
    - SPF/DKIM issues
    """
    advisor = PolicyAdvisor(db)
    recommendations = advisor.get_all_recommendations(days, limit)

    return RecommendationsListResponse(
        total=len(recommendations),
        recommendations=[
            RecommendationResponse(
                type=r.type,
                priority=r.priority,
                domain=r.domain,
                title=r.title,
                description=r.description,
                current_state=r.current_state,
                recommended_action=r.recommended_action,
                impact=r.impact,
                confidence=r.confidence,
            )
            for r in recommendations
        ],
    )


@router.get(
    "/recommendations/{domain}",
    response_model=RecommendationsListResponse,
    summary="Get recommendations for a domain"
)
async def get_domain_recommendations(
    domain: str,
    days: int = Query(default=30, ge=7, le=90, description="Days to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get policy recommendations for a specific domain.

    Includes:
    - Policy upgrade/downgrade recommendation
    - Failing sender recommendations
    """
    advisor = PolicyAdvisor(db)

    recommendations = []

    # Policy recommendation
    policy_rec = advisor.get_policy_recommendation(domain, days)
    if policy_rec:
        recommendations.append(policy_rec)

    # Sender recommendations
    sender_recs = advisor.get_new_sender_recommendations(domain, days)
    recommendations.extend(sender_recs)

    if not recommendations:
        # Check if domain exists
        stats = advisor.get_domain_stats(domain, days)
        if not stats:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for domain: {domain}"
            )

    return RecommendationsListResponse(
        total=len(recommendations),
        recommendations=[
            RecommendationResponse(
                type=r.type,
                priority=r.priority,
                domain=r.domain,
                title=r.title,
                description=r.description,
                current_state=r.current_state,
                recommended_action=r.recommended_action,
                impact=r.impact,
                confidence=r.confidence,
            )
            for r in recommendations
        ],
    )


# ==================== Domain Details ====================

@router.get(
    "/stats/{domain}",
    response_model=DomainStatsResponse,
    summary="Get detailed domain statistics"
)
async def get_domain_stats(
    domain: str,
    days: int = Query(default=30, ge=7, le=90, description="Days to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed statistics for a domain.

    Returns pass rates, policy info, and email volumes.
    """
    advisor = PolicyAdvisor(db)
    stats = advisor.get_domain_stats(domain, days)

    if not stats:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for domain: {domain}"
        )

    return DomainStatsResponse(
        domain=stats['domain'],
        days_analyzed=stats['days_analyzed'],
        total_emails=stats['total_emails'],
        unique_sources=stats['unique_sources'],
        current_policy=stats['current_policy'],
        dkim_pass_rate=stats['dkim_pass_rate'],
        spf_pass_rate=stats['spf_pass_rate'],
        dmarc_pass_rate=stats['dmarc_pass_rate'],
        both_pass_rate=stats['both_pass_rate'],
        both_fail_rate=stats['both_fail_rate'],
        report_count=stats['report_count'],
    )


@router.get(
    "/failing-senders/{domain}",
    response_model=List[FailingSenderResponse],
    summary="Get failing senders for a domain"
)
async def get_failing_senders(
    domain: str,
    days: int = Query(default=30, ge=7, le=90, description="Days to analyze"),
    min_volume: int = Query(default=100, ge=1, description="Minimum email volume"),
    limit: int = Query(default=20, ge=1, le=100, description="Max senders to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get list of senders failing authentication for a domain.

    These may be legitimate senders that need to be authorized.
    Sorted by failure volume (highest first).
    """
    advisor = PolicyAdvisor(db)
    senders = advisor.get_failing_senders(domain, days, min_volume, limit)

    return [FailingSenderResponse(**s) for s in senders]
