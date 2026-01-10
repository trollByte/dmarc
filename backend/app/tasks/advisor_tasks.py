"""
Celery tasks for Policy Advisor scheduled reports.

Tasks:
- send_weekly_advisor_report: Send weekly recommendation email
- send_daily_health_summary: Send daily health summary
"""

import logging
from datetime import datetime
from celery import Task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database import SessionLocal
from app.services.policy_advisor import PolicyAdvisor
from app.config import get_settings

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task with database session management"""
    _db = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


def _build_html_report(
    health: dict,
    recommendations: list,
    domains: list,
    report_type: str = "weekly"
) -> str:
    """Build HTML email report"""

    # Grade colors
    grade_colors = {
        'A': '#22c55e', 'B': '#84cc16', 'C': '#eab308',
        'D': '#f97316', 'F': '#ef4444'
    }

    priority_colors = {
        'critical': '#ef4444', 'high': '#f97316',
        'medium': '#eab308', 'low': '#22c55e', 'info': '#3b82f6'
    }

    policy_icons = {
        'reject': '🛡️', 'quarantine': '⚠️', 'none': '❌'
    }

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header p {{ margin: 10px 0 0; opacity: 0.9; }}
            .content {{ padding: 30px; }}
            .score-card {{ display: flex; justify-content: space-around; background: #f8fafc; border-radius: 8px; padding: 20px; margin-bottom: 30px; }}
            .score-item {{ text-align: center; }}
            .score-value {{ font-size: 36px; font-weight: bold; }}
            .score-label {{ color: #64748b; font-size: 14px; margin-top: 5px; }}
            .section {{ margin-bottom: 30px; }}
            .section h2 {{ color: #1e293b; font-size: 18px; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }}
            .recommendation {{ background: #f8fafc; border-left: 4px solid; padding: 15px; margin-bottom: 15px; border-radius: 0 8px 8px 0; }}
            .rec-title {{ font-weight: 600; margin-bottom: 5px; }}
            .rec-desc {{ color: #64748b; font-size: 14px; margin-bottom: 10px; }}
            .rec-action {{ background: #e0f2fe; color: #0369a1; padding: 8px 12px; border-radius: 4px; font-size: 13px; }}
            .domain-row {{ display: flex; justify-content: space-between; padding: 12px; border-bottom: 1px solid #e2e8f0; }}
            .domain-name {{ font-weight: 500; }}
            .domain-stats {{ color: #64748b; font-size: 14px; }}
            .grade {{ display: inline-block; width: 30px; height: 30px; line-height: 30px; text-align: center; border-radius: 50%; color: white; font-weight: bold; }}
            .footer {{ background: #f8fafc; padding: 20px; text-align: center; color: #64748b; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>DMARC {report_type.title()} Report</h1>
                <p>{datetime.utcnow().strftime('%B %d, %Y')}</p>
            </div>

            <div class="content">
                <div class="score-card">
                    <div class="score-item">
                        <div class="score-value" style="color: {grade_colors.get(health.get('grade', 'C'), '#eab308')}">{health.get('overall_score', 0)}</div>
                        <div class="score-label">Health Score</div>
                    </div>
                    <div class="score-item">
                        <div class="score-value">{health.get('total_domains', 0)}</div>
                        <div class="score-label">Domains</div>
                    </div>
                    <div class="score-item">
                        <div class="score-value">{health.get('total_emails', 0):,}</div>
                        <div class="score-label">Emails Analyzed</div>
                    </div>
                    <div class="score-item">
                        <div class="score-value">{health.get('domains_at_reject', 0)}</div>
                        <div class="score-label">At p=reject</div>
                    </div>
                </div>
    """

    # Recommendations section
    if recommendations:
        html += """
                <div class="section">
                    <h2>🎯 Top Recommendations</h2>
        """
        for rec in recommendations[:10]:
            priority = rec.priority.value if hasattr(rec.priority, 'value') else rec.priority
            color = priority_colors.get(priority, '#3b82f6')
            html += f"""
                    <div class="recommendation" style="border-color: {color}">
                        <div class="rec-title" style="color: {color}">[{priority.upper()}] {rec.title}</div>
                        <div class="rec-desc">{rec.description[:200]}{'...' if len(rec.description) > 200 else ''}</div>
                        <div class="rec-action">👉 {rec.recommended_action}</div>
                    </div>
            """
        html += "</div>"

    # Domains needing attention
    problem_domains = [d for d in domains if d.overall_score < 80][:10]
    if problem_domains:
        html += """
                <div class="section">
                    <h2>⚠️ Domains Needing Attention</h2>
        """
        for d in problem_domains:
            grade_color = grade_colors.get(d.grade, '#eab308')
            policy_icon = policy_icons.get(d.current_policy, '')
            html += f"""
                    <div class="domain-row">
                        <div>
                            <span class="grade" style="background: {grade_color}">{d.grade}</span>
                            <span class="domain-name" style="margin-left: 10px">{d.domain}</span>
                        </div>
                        <div class="domain-stats">
                            {policy_icon} {d.current_policy} | {d.pass_rate:.1%} pass | {d.total_emails:,} emails
                        </div>
                    </div>
            """
        html += "</div>"

    # Policy breakdown
    policy = health.get('policy_breakdown', {})
    html += f"""
                <div class="section">
                    <h2>📊 Policy Distribution</h2>
                    <div class="domain-row">
                        <div>🛡️ <strong>reject</strong> (fully protected)</div>
                        <div>{policy.get('reject', 0)} domains</div>
                    </div>
                    <div class="domain-row">
                        <div>⚠️ <strong>quarantine</strong> (partial protection)</div>
                        <div>{policy.get('quarantine', 0)} domains</div>
                    </div>
                    <div class="domain-row">
                        <div>❌ <strong>none</strong> (monitoring only)</div>
                        <div>{policy.get('none', 0)} domains</div>
                    </div>
                </div>
            </div>

            <div class="footer">
                <p>Generated by DMARC Policy Advisor</p>
                <p>This is an automated report. Do not reply to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """

    return html


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
    name="app.tasks.advisor_tasks.send_weekly_advisor_report"
)
def send_weekly_advisor_report(self, days: int = 30):
    """
    Send weekly DMARC policy advisor report via email.

    **Schedule:** Weekly (Monday 8 AM)

    Args:
        days: Number of days to analyze

    Returns:
        Dictionary with send results
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    logger.info("Generating weekly advisor report")

    settings = get_settings()

    # Check if email is configured
    if not settings.smtp_host or not settings.alert_email_to:
        logger.warning("Email not configured, skipping weekly report")
        return {"status": "skipped", "reason": "email_not_configured"}

    try:
        advisor = PolicyAdvisor(self.db)

        # Gather data
        health = advisor.get_overall_health(days)
        recommendations = advisor.get_all_recommendations(days, limit=20)

        # Get domain health scores
        from app.models import DmarcReport
        domain_names = self.db.query(DmarcReport.domain).distinct().all()
        domains = []
        for (domain,) in domain_names:
            h = advisor.get_domain_health_score(domain, days)
            if h:
                domains.append(h)
        domains.sort(key=lambda x: x.overall_score)

        # Build HTML report
        html = _build_html_report(health, recommendations, domains, "weekly")

        # Send email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"DMARC Weekly Report - Score: {health['overall_score']}/100 ({health['grade']})"
        msg['From'] = settings.smtp_from
        msg['To'] = settings.alert_email_to
        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)

        logger.info(f"Weekly advisor report sent to {settings.alert_email_to}")

        return {
            "status": "success",
            "sent_to": settings.alert_email_to,
            "health_score": health['overall_score'],
            "recommendations": len(recommendations),
            "domains_analyzed": len(domains),
        }

    except Exception as e:
        logger.error(f"Failed to send weekly report: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=3600)


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
    name="app.tasks.advisor_tasks.send_daily_health_summary"
)
def send_daily_health_summary(self, days: int = 7):
    """
    Send daily DMARC health summary via email.

    **Schedule:** Daily (8 AM)

    Sends a brief summary only if there are critical issues.

    Args:
        days: Number of days to analyze

    Returns:
        Dictionary with send results
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    logger.info("Checking daily health summary")

    settings = get_settings()

    if not settings.smtp_host or not settings.alert_email_to:
        logger.warning("Email not configured, skipping daily summary")
        return {"status": "skipped", "reason": "email_not_configured"}

    try:
        advisor = PolicyAdvisor(self.db)
        health = advisor.get_overall_health(days)
        recommendations = advisor.get_all_recommendations(days, limit=50)

        # Only send if there are critical/high priority issues
        critical_recs = [r for r in recommendations
                         if r.priority.value in ['critical', 'high']]

        if not critical_recs:
            logger.info("No critical issues, skipping daily email")
            return {
                "status": "skipped",
                "reason": "no_critical_issues",
                "health_score": health['overall_score'],
            }

        # Get domain health scores
        from app.models import DmarcReport
        domain_names = self.db.query(DmarcReport.domain).distinct().all()
        domains = []
        for (domain,) in domain_names:
            h = advisor.get_domain_health_score(domain, days)
            if h:
                domains.append(h)
        domains.sort(key=lambda x: x.overall_score)

        # Build HTML report
        html = _build_html_report(health, critical_recs, domains, "daily")

        # Send email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"⚠️ DMARC Alert: {len(critical_recs)} Critical Issues Detected"
        msg['From'] = settings.smtp_from
        msg['To'] = settings.alert_email_to
        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)

        logger.info(f"Daily health summary sent to {settings.alert_email_to}")

        return {
            "status": "success",
            "sent_to": settings.alert_email_to,
            "critical_issues": len(critical_recs),
            "health_score": health['overall_score'],
        }

    except Exception as e:
        logger.error(f"Failed to send daily summary: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=3600)
