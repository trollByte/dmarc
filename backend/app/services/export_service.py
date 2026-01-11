"""
Export Service for generating PDF and CSV reports.

Supports:
- DMARC report summaries (PDF/CSV)
- Alert history exports
- Domain health reports
- Compliance reports
"""

import io
import csv
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from app.models import DmarcReport, DmarcRecord, AlertHistory, User
from app.services.policy_advisor import PolicyAdvisor

logger = logging.getLogger(__name__)


class ExportService:
    """Service for exporting data to PDF and CSV formats."""

    def __init__(self, db: Session):
        self.db = db
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom PDF styles"""
        self.styles.add(ParagraphStyle(
            name='Title2',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
        ))
        self.styles.add(ParagraphStyle(
            name='Subtitle',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.grey,
            alignment=TA_CENTER,
            spaceAfter=20,
        ))
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor('#2563eb'),
        ))

    # ==================== CSV Exports ====================

    def export_reports_csv(
        self,
        days: int = 30,
        domain: Optional[str] = None
    ) -> str:
        """Export DMARC reports to CSV format"""
        since = datetime.utcnow() - timedelta(days=days)

        query = self.db.query(DmarcReport).filter(
            DmarcReport.date_begin >= since
        )
        if domain:
            query = query.filter(DmarcReport.domain == domain)

        reports = query.order_by(DmarcReport.date_begin.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Report ID', 'Organization', 'Domain', 'Date Begin', 'Date End',
            'Policy', 'Subdomain Policy', 'DKIM Alignment', 'SPF Alignment',
            'Total Records', 'Total Emails', 'Pass Count', 'Fail Count',
            'Pass Rate %', 'Created At'
        ])

        for report in reports:
            # Calculate stats
            total_records = len(report.records)
            total_emails = sum(r.count for r in report.records)
            pass_count = sum(r.count for r in report.records if r.disposition == 'none')
            fail_count = total_emails - pass_count
            pass_rate = (pass_count / total_emails * 100) if total_emails > 0 else 0

            writer.writerow([
                report.report_id,
                report.org_name,
                report.domain,
                report.date_begin.isoformat() if report.date_begin else '',
                report.date_end.isoformat() if report.date_end else '',
                report.p,
                report.sp or '',
                report.adkim or '',
                report.aspf or '',
                total_records,
                total_emails,
                pass_count,
                fail_count,
                f"{pass_rate:.1f}",
                report.created_at.isoformat() if report.created_at else '',
            ])

        return output.getvalue()

    def export_records_csv(
        self,
        days: int = 30,
        domain: Optional[str] = None
    ) -> str:
        """Export DMARC records to CSV format"""
        since = datetime.utcnow() - timedelta(days=days)

        query = self.db.query(DmarcRecord).join(DmarcReport).filter(
            DmarcReport.date_begin >= since
        )
        if domain:
            query = query.filter(DmarcReport.domain == domain)

        records = query.order_by(DmarcReport.date_begin.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Report ID', 'Domain', 'Source IP', 'Count', 'Disposition',
            'DKIM Result', 'SPF Result', 'Header From', 'Envelope From',
            'DKIM Domain', 'SPF Domain', 'Country', 'Created At'
        ])

        for record in records:
            writer.writerow([
                record.report.report_id if record.report else '',
                record.report.domain if record.report else '',
                record.source_ip,
                record.count,
                record.disposition or '',
                record.dkim or '',
                record.spf or '',
                record.header_from or '',
                record.envelope_from or '',
                record.dkim_domain or '',
                record.spf_domain or '',
                getattr(record, 'country', '') or '',
                record.created_at.isoformat() if record.created_at else '',
            ])

        return output.getvalue()

    def export_alerts_csv(
        self,
        days: int = 30,
        severity: Optional[str] = None
    ) -> str:
        """Export alert history to CSV format"""
        since = datetime.utcnow() - timedelta(days=days)

        query = self.db.query(AlertHistory).filter(
            AlertHistory.created_at >= since
        )
        if severity:
            query = query.filter(AlertHistory.severity == severity)

        alerts = query.order_by(AlertHistory.created_at.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Alert ID', 'Type', 'Severity', 'Status', 'Title',
            'Domain', 'Current Value', 'Threshold', 'Created At',
            'Acknowledged At', 'Resolved At', 'Resolution Note'
        ])

        for alert in alerts:
            writer.writerow([
                str(alert.id),
                alert.alert_type,
                alert.severity,
                alert.status,
                alert.title,
                alert.domain or '',
                alert.current_value or '',
                alert.threshold_value or '',
                alert.created_at.isoformat() if alert.created_at else '',
                alert.acknowledged_at.isoformat() if alert.acknowledged_at else '',
                alert.resolved_at.isoformat() if alert.resolved_at else '',
                alert.resolution_note or '',
            ])

        return output.getvalue()

    def export_recommendations_csv(self, days: int = 30) -> str:
        """Export policy recommendations to CSV"""
        advisor = PolicyAdvisor(self.db)
        recommendations = advisor.get_all_recommendations(days=days, limit=500)

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Domain', 'Priority', 'Category', 'Recommendation',
            'Impact', 'Current Policy', 'Recommended Policy',
            'Pass Rate %', 'Health Score'
        ])

        for rec in recommendations:
            writer.writerow([
                rec.domain,
                rec.priority,
                rec.category,
                rec.recommendation,
                rec.impact,
                rec.current_policy or '',
                rec.recommended_policy or '',
                f"{rec.pass_rate:.1f}" if rec.pass_rate else '',
                rec.health_score or '',
            ])

        return output.getvalue()

    # ==================== PDF Exports ====================

    def export_summary_pdf(
        self,
        days: int = 30,
        domain: Optional[str] = None
    ) -> bytes:
        """Generate PDF summary report"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        story = []
        since = datetime.utcnow() - timedelta(days=days)

        # Title
        story.append(Paragraph("DMARC Summary Report", self.styles['Title2']))
        story.append(Paragraph(
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            self.styles['Subtitle']
        ))
        if domain:
            story.append(Paragraph(f"Domain: {domain}", self.styles['Subtitle']))
        story.append(Paragraph(f"Period: Last {days} days", self.styles['Subtitle']))
        story.append(Spacer(1, 20))

        # Summary Statistics
        story.append(Paragraph("Executive Summary", self.styles['SectionHeader']))

        stats = self._get_summary_stats(days, domain)
        summary_data = [
            ['Metric', 'Value'],
            ['Total Reports', f"{stats['total_reports']:,}"],
            ['Total Emails', f"{stats['total_emails']:,}"],
            ['Overall Pass Rate', f"{stats['pass_rate']:.1f}%"],
            ['Unique Domains', f"{stats['unique_domains']:,}"],
            ['Unique Source IPs', f"{stats['unique_ips']:,}"],
            ['Active Alerts', f"{stats['active_alerts']:,}"],
        ]

        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 20))

        # Top Domains by Volume
        story.append(Paragraph("Top Domains by Volume", self.styles['SectionHeader']))
        top_domains = self._get_top_domains(days, limit=10)

        if top_domains:
            domain_data = [['Domain', 'Emails', 'Pass Rate', 'Policy']]
            for d in top_domains:
                domain_data.append([
                    d['domain'][:40],
                    f"{d['total_emails']:,}",
                    f"{d['pass_rate']:.1f}%",
                    d['policy']
                ])

            domain_table = Table(domain_data, colWidths=[2.5*inch, 1.2*inch, 1*inch, 0.8*inch])
            domain_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
                ('PADDING', (0, 0), (-1, -1), 6),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ]))
            story.append(domain_table)
        else:
            story.append(Paragraph("No data available", self.styles['Normal']))

        story.append(Spacer(1, 20))

        # Top Failing Sources
        story.append(Paragraph("Top Failing Source IPs", self.styles['SectionHeader']))
        failing_ips = self._get_top_failing_ips(days, limit=10)

        if failing_ips:
            ip_data = [['Source IP', 'Failed Emails', 'Domains Affected']]
            for ip in failing_ips:
                ip_data.append([
                    ip['source_ip'],
                    f"{ip['failed_count']:,}",
                    str(ip['domains_affected'])
                ])

            ip_table = Table(ip_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
            ip_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dc2626')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(ip_table)
        else:
            story.append(Paragraph("No failing sources detected", self.styles['Normal']))

        story.append(PageBreak())

        # Recommendations
        story.append(Paragraph("Policy Recommendations", self.styles['SectionHeader']))
        advisor = PolicyAdvisor(self.db)
        recommendations = advisor.get_all_recommendations(days=days, limit=10)

        if recommendations:
            for rec in recommendations:
                story.append(Paragraph(
                    f"<b>{rec.domain}</b> - {rec.recommendation}",
                    self.styles['Normal']
                ))
                story.append(Paragraph(
                    f"<i>Priority: {rec.priority} | Impact: {rec.impact}</i>",
                    self.styles['Normal']
                ))
                story.append(Spacer(1, 10))
        else:
            story.append(Paragraph("No recommendations at this time.", self.styles['Normal']))

        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    def export_health_report_pdf(self, domain: str, days: int = 30) -> bytes:
        """Generate domain health report PDF"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)

        story = []
        advisor = PolicyAdvisor(self.db)

        # Get health score
        health = advisor.get_domain_health_score(domain, days)

        # Title
        story.append(Paragraph(f"Domain Health Report", self.styles['Title2']))
        story.append(Paragraph(domain, self.styles['Subtitle']))
        story.append(Paragraph(
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            self.styles['Subtitle']
        ))
        story.append(Spacer(1, 30))

        # Health Score
        grade_colors = {
            'A': '#22c55e', 'B': '#84cc16', 'C': '#eab308',
            'D': '#f97316', 'F': '#ef4444'
        }
        grade_color = grade_colors.get(health.grade, '#6b7280')

        story.append(Paragraph("Health Score", self.styles['SectionHeader']))
        score_data = [
            ['Score', 'Grade', 'Status'],
            [f"{health.score}/100", health.grade, health.status.replace('_', ' ').title()]
        ]
        score_table = Table(score_data, colWidths=[2*inch, 1.5*inch, 2*inch])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, -1), 16),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('PADDING', (0, 0), (-1, -1), 12),
        ]))
        story.append(score_table)
        story.append(Spacer(1, 20))

        # Metrics
        story.append(Paragraph("Key Metrics", self.styles['SectionHeader']))
        metrics_data = [
            ['Metric', 'Value'],
            ['Total Emails', f"{health.total_emails:,}"],
            ['DMARC Pass Rate', f"{health.dmarc_pass_rate:.1f}%"],
            ['DKIM Pass Rate', f"{health.dkim_pass_rate:.1f}%"],
            ['SPF Pass Rate', f"{health.spf_pass_rate:.1f}%"],
            ['Current Policy', health.policy or 'Not set'],
            ['Unique Sources', f"{health.unique_sources:,}"],
        ]
        metrics_table = Table(metrics_data, colWidths=[3*inch, 2.5*inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ]))
        story.append(metrics_table)
        story.append(Spacer(1, 20))

        # Issues
        if health.issues:
            story.append(Paragraph("Issues Detected", self.styles['SectionHeader']))
            for issue in health.issues:
                story.append(Paragraph(f"• {issue}", self.styles['Normal']))
            story.append(Spacer(1, 20))

        # Recommendations
        story.append(Paragraph("Recommendations", self.styles['SectionHeader']))
        rec = advisor.get_policy_recommendation(domain, days)
        if rec:
            story.append(Paragraph(f"<b>{rec.recommendation}</b>", self.styles['Normal']))
            story.append(Paragraph(f"Priority: {rec.priority} | Impact: {rec.impact}", self.styles['Normal']))
            if rec.current_policy and rec.recommended_policy:
                story.append(Paragraph(
                    f"Current: {rec.current_policy} → Recommended: {rec.recommended_policy}",
                    self.styles['Normal']
                ))
        else:
            story.append(Paragraph("No recommendations at this time.", self.styles['Normal']))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    # ==================== Helper Methods ====================

    def _get_summary_stats(self, days: int, domain: Optional[str] = None) -> Dict:
        """Get summary statistics for PDF"""
        since = datetime.utcnow() - timedelta(days=days)

        query = self.db.query(DmarcReport).filter(DmarcReport.date_begin >= since)
        if domain:
            query = query.filter(DmarcReport.domain == domain)

        reports = query.all()

        total_emails = 0
        pass_count = 0
        unique_ips = set()

        for report in reports:
            for record in report.records:
                total_emails += record.count
                if record.disposition == 'none':
                    pass_count += record.count
                unique_ips.add(record.source_ip)

        active_alerts = self.db.query(AlertHistory).filter(
            AlertHistory.resolved_at.is_(None)
        ).count()

        unique_domains = self.db.query(func.count(func.distinct(DmarcReport.domain))).filter(
            DmarcReport.date_begin >= since
        ).scalar() or 0

        return {
            'total_reports': len(reports),
            'total_emails': total_emails,
            'pass_rate': (pass_count / total_emails * 100) if total_emails > 0 else 0,
            'unique_domains': unique_domains,
            'unique_ips': len(unique_ips),
            'active_alerts': active_alerts,
        }

    def _get_top_domains(self, days: int, limit: int = 10) -> List[Dict]:
        """Get top domains by volume"""
        since = datetime.utcnow() - timedelta(days=days)

        results = self.db.query(
            DmarcReport.domain,
            DmarcReport.p,
            func.sum(DmarcRecord.count).label('total'),
            func.sum(
                func.case(
                    (DmarcRecord.disposition == 'none', DmarcRecord.count),
                    else_=0
                )
            ).label('passed')
        ).join(DmarcRecord).filter(
            DmarcReport.date_begin >= since
        ).group_by(
            DmarcReport.domain, DmarcReport.p
        ).order_by(
            func.sum(DmarcRecord.count).desc()
        ).limit(limit).all()

        return [
            {
                'domain': r.domain,
                'total_emails': r.total or 0,
                'pass_rate': ((r.passed or 0) / r.total * 100) if r.total else 0,
                'policy': r.p or 'none'
            }
            for r in results
        ]

    def _get_top_failing_ips(self, days: int, limit: int = 10) -> List[Dict]:
        """Get top failing source IPs"""
        since = datetime.utcnow() - timedelta(days=days)

        results = self.db.query(
            DmarcRecord.source_ip,
            func.sum(DmarcRecord.count).label('failed_count'),
            func.count(func.distinct(DmarcReport.domain)).label('domains')
        ).join(DmarcReport).filter(
            DmarcReport.date_begin >= since,
            DmarcRecord.disposition != 'none'
        ).group_by(
            DmarcRecord.source_ip
        ).order_by(
            func.sum(DmarcRecord.count).desc()
        ).limit(limit).all()

        return [
            {
                'source_ip': r.source_ip,
                'failed_count': r.failed_count or 0,
                'domains_affected': r.domains or 0
            }
            for r in results
        ]
