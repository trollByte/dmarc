"""
Dashboard API routes.

Provides aggregated metrics for frontend dashboard widgets.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models import User, DmarcReport as Report, DmarcRecord as Record, AlertHistory as Alert
from app.services.policy_advisor import PolicyAdvisor
from app.services.threat_intel import ThreatIntelService, ThreatLevel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", summary="Get dashboard summary")
async def get_dashboard_summary(
    days: int = Query(default=7, ge=1, le=90, description="Days of data to include"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get aggregated dashboard summary with all key metrics.

    Returns:
    - Overall health score and grade
    - Email volume statistics (total, passed, failed)
    - Alert counts by severity
    - Top threat IPs
    - Domain count and problem domains
    - Trend indicators (compared to previous period)
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    prev_cutoff = cutoff_date - timedelta(days=days)

    # --- Email Volume Stats ---
    current_stats = db.query(
        func.sum(Record.count).label("total"),
        func.sum(
            func.case(
                (Record.dkim_result == "pass", Record.count),
                else_=0
            )
        ).label("dkim_pass"),
        func.sum(
            func.case(
                (Record.spf_result == "pass", Record.count),
                else_=0
            )
        ).label("spf_pass"),
    ).join(Report).filter(
        Report.date_range_begin >= cutoff_date
    ).first()

    total_emails = current_stats.total or 0
    dkim_pass = current_stats.dkim_pass or 0
    spf_pass = current_stats.spf_pass or 0

    # Calculate pass/fail (email passes if both DKIM and SPF pass for simplicity)
    # More accurate: check policy_evaluated disposition
    pass_stats = db.query(
        func.sum(Record.count).label("passed")
    ).join(Report).filter(
        Report.date_range_begin >= cutoff_date,
        Record.disposition == "none"  # none = delivered (pass)
    ).first()

    passed_emails = pass_stats.passed or 0
    failed_emails = total_emails - passed_emails
    pass_rate = (passed_emails / total_emails * 100) if total_emails > 0 else 0

    # Previous period for trends
    prev_stats = db.query(
        func.sum(Record.count).label("total")
    ).join(Report).filter(
        Report.date_range_begin >= prev_cutoff,
        Report.date_range_begin < cutoff_date
    ).first()

    prev_total = prev_stats.total or 0
    volume_trend = ((total_emails - prev_total) / prev_total * 100) if prev_total > 0 else 0

    # --- Domain Stats ---
    domain_count = db.query(func.count(func.distinct(Report.domain))).filter(
        Report.date_range_begin >= cutoff_date
    ).scalar() or 0

    # --- Alert Stats ---
    alert_counts = db.query(
        Alert.severity,
        func.count(Alert.id)
    ).filter(
        Alert.created_at >= cutoff_date
    ).group_by(Alert.severity).all()

    alerts_by_severity = {
        "critical": 0,
        "warning": 0,
        "info": 0
    }
    total_alerts = 0
    for severity, count in alert_counts:
        if severity in alerts_by_severity:
            alerts_by_severity[severity] = count
            total_alerts += count

    # Unresolved alerts
    unresolved_alerts = db.query(func.count(Alert.id)).filter(
        Alert.resolved_at.is_(None)
    ).scalar() or 0

    # --- Health Score ---
    advisor = PolicyAdvisor(db)
    overall_health = advisor.get_overall_health(days=days)

    # --- Threat Intel Stats ---
    threat_service = ThreatIntelService(db)
    threat_stats = threat_service.get_cache_stats()
    high_threat_ips = threat_service.get_high_threat_ips(min_score=50)[:5]

    top_threats = [
        {
            "ip_address": ip.ip_address,
            "abuse_score": ip.abuse_score,
            "threat_level": ip.threat_level,
            "country_code": ip.country_code,
            "isp": ip.isp,
        }
        for ip in high_threat_ips
    ]

    # --- Recent Reports ---
    recent_reports = db.query(func.count(Report.id)).filter(
        Report.created_at >= datetime.utcnow() - timedelta(hours=24)
    ).scalar() or 0

    # --- Build Response ---
    return {
        "period": {
            "days": days,
            "start_date": cutoff_date.isoformat(),
            "end_date": datetime.utcnow().isoformat(),
        },
        "health": {
            "score": overall_health.get("average_score", 0),
            "grade": overall_health.get("grade", "N/A"),
            "status": _score_to_status(overall_health.get("average_score", 0)),
        },
        "email_volume": {
            "total": total_emails,
            "passed": passed_emails,
            "failed": failed_emails,
            "pass_rate": round(pass_rate, 1),
            "dkim_pass_rate": round((dkim_pass / total_emails * 100) if total_emails > 0 else 0, 1),
            "spf_pass_rate": round((spf_pass / total_emails * 100) if total_emails > 0 else 0, 1),
            "trend_percent": round(volume_trend, 1),
            "trend_direction": "up" if volume_trend > 0 else "down" if volume_trend < 0 else "stable",
        },
        "domains": {
            "total": domain_count,
            "healthy": overall_health.get("healthy_domains", 0),
            "at_risk": overall_health.get("at_risk_domains", 0),
            "critical": overall_health.get("critical_domains", 0),
        },
        "alerts": {
            "total": total_alerts,
            "unresolved": unresolved_alerts,
            "critical": alerts_by_severity["critical"],
            "warning": alerts_by_severity["warning"],
            "info": alerts_by_severity["info"],
        },
        "threats": {
            "cached_ips": threat_stats.get("active_entries", 0),
            "api_configured": threat_stats.get("api_configured", False),
            "top_threats": top_threats,
        },
        "activity": {
            "reports_last_24h": recent_reports,
            "recommendations_count": overall_health.get("total_recommendations", 0),
        },
    }


@router.get("/charts/volume", summary="Get volume chart data")
async def get_volume_chart(
    days: int = Query(default=30, ge=7, le=90, description="Days of data"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get daily email volume data for charts.

    Returns time-series data with daily totals, pass/fail counts.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Get daily aggregates
    daily_stats = db.query(
        func.date(Report.date_range_begin).label("date"),
        func.sum(Record.count).label("total"),
        func.sum(
            func.case(
                (Record.disposition == "none", Record.count),
                else_=0
            )
        ).label("passed"),
    ).join(Record).filter(
        Report.date_range_begin >= cutoff_date
    ).group_by(
        func.date(Report.date_range_begin)
    ).order_by(
        func.date(Report.date_range_begin)
    ).all()

    data_points = []
    for row in daily_stats:
        total = row.total or 0
        passed = row.passed or 0
        data_points.append({
            "date": row.date.isoformat() if row.date else None,
            "total": total,
            "passed": passed,
            "failed": total - passed,
        })

    return {
        "period_days": days,
        "data": data_points,
    }


@router.get("/charts/authentication", summary="Get authentication results chart")
async def get_auth_chart(
    days: int = Query(default=30, ge=7, le=90, description="Days of data"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get authentication results breakdown for charts.

    Returns daily DKIM/SPF pass/fail rates.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    daily_auth = db.query(
        func.date(Report.date_range_begin).label("date"),
        func.sum(Record.count).label("total"),
        func.sum(
            func.case(
                (Record.dkim_result == "pass", Record.count),
                else_=0
            )
        ).label("dkim_pass"),
        func.sum(
            func.case(
                (Record.spf_result == "pass", Record.count),
                else_=0
            )
        ).label("spf_pass"),
    ).join(Record).filter(
        Report.date_range_begin >= cutoff_date
    ).group_by(
        func.date(Report.date_range_begin)
    ).order_by(
        func.date(Report.date_range_begin)
    ).all()

    data_points = []
    for row in daily_auth:
        total = row.total or 0
        data_points.append({
            "date": row.date.isoformat() if row.date else None,
            "dkim_pass_rate": round((row.dkim_pass or 0) / total * 100, 1) if total > 0 else 0,
            "spf_pass_rate": round((row.spf_pass or 0) / total * 100, 1) if total > 0 else 0,
        })

    return {
        "period_days": days,
        "data": data_points,
    }


@router.get("/charts/top-senders", summary="Get top senders")
async def get_top_senders(
    days: int = Query(default=7, ge=1, le=30, description="Days of data"),
    limit: int = Query(default=10, ge=1, le=50, description="Number of senders"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get top sending IP addresses by volume.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    top_senders = db.query(
        Record.source_ip,
        func.sum(Record.count).label("total"),
        func.sum(
            func.case(
                (Record.disposition == "none", Record.count),
                else_=0
            )
        ).label("passed"),
    ).join(Report).filter(
        Report.date_range_begin >= cutoff_date
    ).group_by(
        Record.source_ip
    ).order_by(
        func.sum(Record.count).desc()
    ).limit(limit).all()

    senders = []
    for row in top_senders:
        total = row.total or 0
        passed = row.passed or 0
        senders.append({
            "ip_address": row.source_ip,
            "total_emails": total,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
        })

    return {
        "period_days": days,
        "senders": senders,
    }


@router.get("/charts/geo-distribution", summary="Get geographic distribution")
async def get_geo_distribution(
    days: int = Query(default=7, ge=1, le=30, description="Days of data"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get email volume by country (requires geolocation data).
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    geo_stats = db.query(
        Record.country,
        func.sum(Record.count).label("total"),
    ).join(Report).filter(
        Report.date_range_begin >= cutoff_date,
        Record.country.isnot(None)
    ).group_by(
        Record.country
    ).order_by(
        func.sum(Record.count).desc()
    ).limit(20).all()

    countries = [
        {
            "country_code": row.country,
            "total_emails": row.total or 0,
        }
        for row in geo_stats
    ]

    return {
        "period_days": days,
        "countries": countries,
    }


def _score_to_status(score: float) -> str:
    """Convert health score to status label"""
    if score >= 90:
        return "excellent"
    elif score >= 70:
        return "good"
    elif score >= 50:
        return "fair"
    elif score >= 30:
        return "poor"
    else:
        return "critical"
