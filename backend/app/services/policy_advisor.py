"""
DMARC Policy Advisor Service

Analyzes DMARC data and provides actionable recommendations for:
- Policy upgrades (none → quarantine → reject)
- New sender authorization
- SPF/DKIM alignment improvements
- Domain health scoring
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case

from app.models import DmarcReport, DmarcRecord

logger = logging.getLogger(__name__)


class RecommendationType(str, Enum):
    """Types of recommendations"""
    POLICY_UPGRADE = "policy_upgrade"
    POLICY_DOWNGRADE = "policy_downgrade"
    NEW_SENDER = "new_sender"
    SPF_ISSUE = "spf_issue"
    DKIM_ISSUE = "dkim_issue"
    ALIGNMENT_ISSUE = "alignment_issue"
    LOW_VOLUME = "low_volume"
    HIGH_FAILURE = "high_failure"


class RecommendationPriority(str, Enum):
    """Priority levels for recommendations"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Recommendation:
    """A policy recommendation"""
    type: RecommendationType
    priority: RecommendationPriority
    domain: str
    title: str
    description: str
    current_state: Dict[str, Any]
    recommended_action: str
    impact: str
    confidence: float  # 0-1 confidence in this recommendation


@dataclass
class DomainHealthScore:
    """Health score for a domain"""
    domain: str
    overall_score: int  # 0-100
    pass_rate: float
    spf_alignment_rate: float
    dkim_alignment_rate: float
    current_policy: str
    recommended_policy: str
    total_emails: int
    total_sources: int
    issues: List[str]
    grade: str  # A, B, C, D, F


class PolicyAdvisor:
    """
    Analyzes DMARC data and provides policy recommendations.
    """

    # Thresholds for policy recommendations
    POLICY_UPGRADE_THRESHOLD = 0.98  # 98% pass rate to recommend upgrade
    POLICY_SAFE_THRESHOLD = 0.95     # 95% for cautious upgrade
    POLICY_CONCERN_THRESHOLD = 0.90  # Below 90% is concerning
    MIN_EMAILS_FOR_RECOMMENDATION = 1000  # Minimum emails needed
    MIN_DAYS_FOR_RECOMMENDATION = 14  # Minimum days of data

    # Thresholds for sender recommendations
    NEW_SENDER_MIN_VOLUME = 100  # Min emails to flag a sender
    NEW_SENDER_FAILURE_THRESHOLD = 0.80  # 80% failure rate

    def __init__(self, db: Session):
        self.db = db

    def get_domain_stats(
        self,
        domain: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a domain.

        Args:
            domain: Domain to analyze
            days: Number of days to analyze

        Returns:
            Dictionary with domain statistics
        """
        since = datetime.utcnow() - timedelta(days=days)

        # Get reports for this domain
        reports = self.db.query(DmarcReport).filter(
            DmarcReport.domain == domain,
            DmarcReport.date_begin >= since
        ).all()

        if not reports:
            return None

        report_ids = [r.id for r in reports]

        # Aggregate record stats
        stats = self.db.query(
            func.sum(DmarcRecord.count).label('total_emails'),
            func.sum(case((DmarcRecord.dkim == 'pass', DmarcRecord.count), else_=0)).label('dkim_pass'),
            func.sum(case((DmarcRecord.spf == 'pass', DmarcRecord.count), else_=0)).label('spf_pass'),
            func.sum(case(
                (and_(DmarcRecord.dkim == 'pass', DmarcRecord.spf == 'pass'), DmarcRecord.count),
                else_=0
            )).label('both_pass'),
            func.sum(case(
                (and_(DmarcRecord.dkim == 'fail', DmarcRecord.spf == 'fail'), DmarcRecord.count),
                else_=0
            )).label('both_fail'),
            func.count(func.distinct(DmarcRecord.source_ip)).label('unique_sources'),
        ).filter(DmarcRecord.report_id.in_(report_ids)).first()

        total = stats.total_emails or 0
        if total == 0:
            return None

        # Get current policy from most recent report
        latest_report = max(reports, key=lambda r: r.date_begin)
        current_policy = latest_report.p or 'none'

        # Calculate pass rate (DMARC pass = DKIM pass OR SPF pass)
        dkim_pass = stats.dkim_pass or 0
        spf_pass = stats.spf_pass or 0
        both_fail = stats.both_fail or 0

        # DMARC passes if either DKIM or SPF passes
        dmarc_pass = total - both_fail
        pass_rate = dmarc_pass / total if total > 0 else 0

        return {
            'domain': domain,
            'days_analyzed': days,
            'total_emails': total,
            'unique_sources': stats.unique_sources or 0,
            'current_policy': current_policy,
            'dkim_pass_rate': dkim_pass / total if total > 0 else 0,
            'spf_pass_rate': spf_pass / total if total > 0 else 0,
            'dmarc_pass_rate': pass_rate,
            'both_pass_rate': (stats.both_pass or 0) / total if total > 0 else 0,
            'both_fail_rate': both_fail / total if total > 0 else 0,
            'first_report': min(r.date_begin for r in reports),
            'last_report': max(r.date_end for r in reports),
            'report_count': len(reports),
        }

    def get_domain_health_score(
        self,
        domain: str,
        days: int = 30
    ) -> Optional[DomainHealthScore]:
        """
        Calculate health score for a domain.

        Args:
            domain: Domain to analyze
            days: Number of days to analyze

        Returns:
            DomainHealthScore object or None if no data
        """
        stats = self.get_domain_stats(domain, days)
        if not stats:
            return None

        issues = []
        score = 100

        pass_rate = stats['dmarc_pass_rate']
        dkim_rate = stats['dkim_pass_rate']
        spf_rate = stats['spf_pass_rate']
        policy = stats['current_policy']

        # Deduct points for low pass rates
        if pass_rate < 0.90:
            score -= 30
            issues.append(f"Low DMARC pass rate: {pass_rate:.1%}")
        elif pass_rate < 0.95:
            score -= 15
            issues.append(f"DMARC pass rate could be improved: {pass_rate:.1%}")
        elif pass_rate < 0.98:
            score -= 5

        # Deduct for weak policy
        if policy == 'none':
            score -= 25
            issues.append("Policy is 'none' - emails are not protected")
        elif policy == 'quarantine':
            score -= 10
            issues.append("Policy is 'quarantine' - consider upgrading to 'reject'")

        # Deduct for alignment issues
        if dkim_rate < 0.90:
            score -= 10
            issues.append(f"DKIM alignment issues: {dkim_rate:.1%} pass rate")

        if spf_rate < 0.90:
            score -= 10
            issues.append(f"SPF alignment issues: {spf_rate:.1%} pass rate")

        # Deduct for low volume (less confidence)
        if stats['total_emails'] < 1000:
            score -= 5
            issues.append(f"Low email volume ({stats['total_emails']:,}) - limited data")

        # Ensure score is within bounds
        score = max(0, min(100, score))

        # Calculate grade
        if score >= 90:
            grade = 'A'
        elif score >= 80:
            grade = 'B'
        elif score >= 70:
            grade = 'C'
        elif score >= 60:
            grade = 'D'
        else:
            grade = 'F'

        # Determine recommended policy
        if pass_rate >= self.POLICY_UPGRADE_THRESHOLD:
            if policy == 'none':
                recommended = 'quarantine'
            elif policy == 'quarantine':
                recommended = 'reject'
            else:
                recommended = 'reject'
        elif pass_rate >= self.POLICY_SAFE_THRESHOLD:
            if policy == 'none':
                recommended = 'quarantine'
            else:
                recommended = policy
        else:
            recommended = policy  # Don't recommend upgrade with low pass rate

        return DomainHealthScore(
            domain=domain,
            overall_score=score,
            pass_rate=pass_rate,
            spf_alignment_rate=spf_rate,
            dkim_alignment_rate=dkim_rate,
            current_policy=policy,
            recommended_policy=recommended,
            total_emails=stats['total_emails'],
            total_sources=stats['unique_sources'],
            issues=issues,
            grade=grade,
        )

    def get_policy_recommendation(
        self,
        domain: str,
        days: int = 30
    ) -> Optional[Recommendation]:
        """
        Generate policy upgrade/downgrade recommendation for a domain.

        Args:
            domain: Domain to analyze
            days: Number of days to analyze

        Returns:
            Recommendation object or None
        """
        stats = self.get_domain_stats(domain, days)
        if not stats:
            return None

        pass_rate = stats['dmarc_pass_rate']
        total_emails = stats['total_emails']
        current_policy = stats['current_policy']

        # Not enough data
        if total_emails < self.MIN_EMAILS_FOR_RECOMMENDATION:
            return Recommendation(
                type=RecommendationType.LOW_VOLUME,
                priority=RecommendationPriority.INFO,
                domain=domain,
                title=f"Insufficient data for {domain}",
                description=f"Only {total_emails:,} emails analyzed. Need at least {self.MIN_EMAILS_FOR_RECOMMENDATION:,} for reliable recommendations.",
                current_state={'total_emails': total_emails, 'policy': current_policy},
                recommended_action="Continue monitoring until more data is available",
                impact="Unable to make policy recommendations with confidence",
                confidence=0.3,
            )

        # Check for policy upgrade opportunity
        if pass_rate >= self.POLICY_UPGRADE_THRESHOLD:
            if current_policy == 'none':
                return Recommendation(
                    type=RecommendationType.POLICY_UPGRADE,
                    priority=RecommendationPriority.HIGH,
                    domain=domain,
                    title=f"Upgrade {domain} to quarantine policy",
                    description=f"Excellent pass rate of {pass_rate:.1%} over {days} days with {total_emails:,} emails. Domain is ready for stricter policy.",
                    current_state={
                        'policy': current_policy,
                        'pass_rate': pass_rate,
                        'total_emails': total_emails,
                    },
                    recommended_action="Update DMARC record to p=quarantine",
                    impact="Suspicious emails will be quarantined instead of delivered",
                    confidence=0.95,
                )
            elif current_policy == 'quarantine':
                return Recommendation(
                    type=RecommendationType.POLICY_UPGRADE,
                    priority=RecommendationPriority.MEDIUM,
                    domain=domain,
                    title=f"Upgrade {domain} to reject policy",
                    description=f"Strong pass rate of {pass_rate:.1%} with quarantine policy. Domain is ready for full protection.",
                    current_state={
                        'policy': current_policy,
                        'pass_rate': pass_rate,
                        'total_emails': total_emails,
                    },
                    recommended_action="Update DMARC record to p=reject",
                    impact="Unauthorized emails will be rejected entirely",
                    confidence=0.90,
                )

        # Check for concerning pass rate
        elif pass_rate < self.POLICY_CONCERN_THRESHOLD:
            if current_policy in ['quarantine', 'reject']:
                return Recommendation(
                    type=RecommendationType.HIGH_FAILURE,
                    priority=RecommendationPriority.CRITICAL,
                    domain=domain,
                    title=f"High failure rate for {domain}",
                    description=f"Only {pass_rate:.1%} of emails are passing DMARC. Legitimate emails may be blocked.",
                    current_state={
                        'policy': current_policy,
                        'pass_rate': pass_rate,
                        'total_emails': total_emails,
                        'failure_rate': 1 - pass_rate,
                    },
                    recommended_action="Investigate failing sources - may need to authorize legitimate senders",
                    impact="Legitimate emails may be quarantined or rejected",
                    confidence=0.85,
                )

        return None

    def get_failing_senders(
        self,
        domain: str,
        days: int = 30,
        min_volume: int = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get top senders that are failing authentication.

        These might be legitimate senders that need to be authorized.

        Args:
            domain: Domain to analyze
            days: Number of days to analyze
            min_volume: Minimum email volume to include
            limit: Maximum senders to return

        Returns:
            List of failing sender details
        """
        if min_volume is None:
            min_volume = self.NEW_SENDER_MIN_VOLUME

        since = datetime.utcnow() - timedelta(days=days)

        # Get reports for this domain
        report_ids = self.db.query(DmarcReport.id).filter(
            DmarcReport.domain == domain,
            DmarcReport.date_begin >= since
        ).all()
        report_ids = [r[0] for r in report_ids]

        if not report_ids:
            return []

        # Find sources with high failure rates
        results = self.db.query(
            DmarcRecord.source_ip,
            func.sum(DmarcRecord.count).label('total'),
            func.sum(case((DmarcRecord.dkim == 'pass', DmarcRecord.count), else_=0)).label('dkim_pass'),
            func.sum(case((DmarcRecord.spf == 'pass', DmarcRecord.count), else_=0)).label('spf_pass'),
            func.sum(case(
                (and_(DmarcRecord.dkim == 'fail', DmarcRecord.spf == 'fail'), DmarcRecord.count),
                else_=0
            )).label('both_fail'),
        ).filter(
            DmarcRecord.report_id.in_(report_ids)
        ).group_by(
            DmarcRecord.source_ip
        ).having(
            func.sum(DmarcRecord.count) >= min_volume
        ).order_by(
            func.sum(case(
                (and_(DmarcRecord.dkim == 'fail', DmarcRecord.spf == 'fail'), DmarcRecord.count),
                else_=0
            )).desc()
        ).limit(limit).all()

        failing_senders = []
        for row in results:
            total = row.total or 0
            both_fail = row.both_fail or 0

            if total == 0:
                continue

            failure_rate = both_fail / total

            # Only include if failure rate is significant
            if failure_rate >= 0.10:  # At least 10% failure
                failing_senders.append({
                    'source_ip': row.source_ip,
                    'total_emails': total,
                    'dkim_pass': row.dkim_pass or 0,
                    'spf_pass': row.spf_pass or 0,
                    'both_fail': both_fail,
                    'failure_rate': failure_rate,
                    'dkim_pass_rate': (row.dkim_pass or 0) / total,
                    'spf_pass_rate': (row.spf_pass or 0) / total,
                })

        return failing_senders

    def get_new_sender_recommendations(
        self,
        domain: str,
        days: int = 30
    ) -> List[Recommendation]:
        """
        Generate recommendations for new/failing senders.

        Args:
            domain: Domain to analyze
            days: Number of days to analyze

        Returns:
            List of Recommendation objects
        """
        failing_senders = self.get_failing_senders(domain, days)
        recommendations = []

        for sender in failing_senders[:10]:  # Top 10
            ip = sender['source_ip']
            total = sender['total_emails']
            failure_rate = sender['failure_rate']

            # Determine issue type
            if sender['dkim_pass_rate'] < 0.5 and sender['spf_pass_rate'] < 0.5:
                issue_type = RecommendationType.ALIGNMENT_ISSUE
                issue_desc = "Both SPF and DKIM failing"
                action = f"Investigate IP {ip} - if legitimate, add to SPF record and configure DKIM"
            elif sender['dkim_pass_rate'] < 0.5:
                issue_type = RecommendationType.DKIM_ISSUE
                issue_desc = "DKIM failing"
                action = f"Configure DKIM signing for sender {ip}"
            else:
                issue_type = RecommendationType.SPF_ISSUE
                issue_desc = "SPF failing"
                action = f"Add {ip} to SPF record if this is a legitimate sender"

            # Determine priority based on volume and failure rate
            if total >= 10000 and failure_rate >= 0.5:
                priority = RecommendationPriority.CRITICAL
            elif total >= 1000 or failure_rate >= 0.8:
                priority = RecommendationPriority.HIGH
            elif total >= 100:
                priority = RecommendationPriority.MEDIUM
            else:
                priority = RecommendationPriority.LOW

            recommendations.append(Recommendation(
                type=issue_type,
                priority=priority,
                domain=domain,
                title=f"Failing sender: {ip}",
                description=f"{issue_desc} for {total:,} emails ({failure_rate:.1%} failure rate). This may be a legitimate sender that needs authorization.",
                current_state={
                    'source_ip': ip,
                    'total_emails': total,
                    'failure_rate': failure_rate,
                    'dkim_pass_rate': sender['dkim_pass_rate'],
                    'spf_pass_rate': sender['spf_pass_rate'],
                },
                recommended_action=action,
                impact=f"Could prevent {int(total * failure_rate):,} emails from being properly authenticated",
                confidence=0.75,
            ))

        return recommendations

    def get_all_recommendations(
        self,
        days: int = 30,
        limit: int = 50
    ) -> List[Recommendation]:
        """
        Get all recommendations across all domains.

        Args:
            days: Number of days to analyze
            limit: Maximum recommendations to return

        Returns:
            List of Recommendation objects sorted by priority
        """
        # Get all domains
        domains = self.db.query(DmarcReport.domain).distinct().all()
        domains = [d[0] for d in domains]

        all_recommendations = []

        for domain in domains:
            # Policy recommendation
            policy_rec = self.get_policy_recommendation(domain, days)
            if policy_rec:
                all_recommendations.append(policy_rec)

            # Sender recommendations (limit per domain)
            sender_recs = self.get_new_sender_recommendations(domain, days)
            all_recommendations.extend(sender_recs[:3])  # Top 3 per domain

        # Sort by priority
        priority_order = {
            RecommendationPriority.CRITICAL: 0,
            RecommendationPriority.HIGH: 1,
            RecommendationPriority.MEDIUM: 2,
            RecommendationPriority.LOW: 3,
            RecommendationPriority.INFO: 4,
        }

        all_recommendations.sort(key=lambda r: (priority_order[r.priority], -r.confidence))

        return all_recommendations[:limit]

    def get_overall_health(self, days: int = 30) -> Dict[str, Any]:
        """
        Get overall health summary across all domains.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with overall health metrics
        """
        domains = self.db.query(DmarcReport.domain).distinct().all()
        domains = [d[0] for d in domains]

        if not domains:
            return {
                'total_domains': 0,
                'overall_score': 0,
                'grade': 'N/A',
            }

        scores = []
        policy_breakdown = {'none': 0, 'quarantine': 0, 'reject': 0}
        grade_breakdown = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        total_emails = 0
        total_sources = 0

        for domain in domains:
            health = self.get_domain_health_score(domain, days)
            if health:
                scores.append(health.overall_score)
                policy_breakdown[health.current_policy] = policy_breakdown.get(health.current_policy, 0) + 1
                grade_breakdown[health.grade] = grade_breakdown.get(health.grade, 0) + 1
                total_emails += health.total_emails
                total_sources += health.total_sources

        avg_score = sum(scores) / len(scores) if scores else 0

        # Overall grade
        if avg_score >= 90:
            overall_grade = 'A'
        elif avg_score >= 80:
            overall_grade = 'B'
        elif avg_score >= 70:
            overall_grade = 'C'
        elif avg_score >= 60:
            overall_grade = 'D'
        else:
            overall_grade = 'F'

        return {
            'total_domains': len(domains),
            'analyzed_domains': len(scores),
            'overall_score': round(avg_score, 1),
            'grade': overall_grade,
            'total_emails': total_emails,
            'total_sources': total_sources,
            'policy_breakdown': policy_breakdown,
            'grade_breakdown': grade_breakdown,
            'domains_at_reject': policy_breakdown.get('reject', 0),
            'domains_needing_upgrade': policy_breakdown.get('none', 0) + policy_breakdown.get('quarantine', 0),
        }
