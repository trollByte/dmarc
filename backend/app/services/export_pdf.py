"""
PDF Export Service

Generates comprehensive PDF reports for DMARC data with charts and tables
"""
import io
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from app.models import DmarcReport, DmarcRecord


class PDFExportService:
    """Service for generating PDF reports"""

    def __init__(self, db: Session):
        self.db = db
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))

        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#7f8c8d'),
            spaceAfter=20,
            alignment=TA_CENTER
        ))

        # Section heading
        self.styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=12,
            spaceBefore=12
        ))

    def generate_summary_report(
        self,
        domain: Optional[str] = None,
        days: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> bytes:
        """
        Generate comprehensive PDF summary report

        Args:
            domain: Filter by domain
            days: Number of days to include
            start_date: Start date for filtering
            end_date: End date for filtering

        Returns:
            PDF bytes
        """
        # Create PDF buffer
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )

        # Container for PDF elements
        story = []

        # Title Page
        story.append(Paragraph("DMARC Summary Report", self.styles['CustomTitle']))

        # Subtitle with filters
        subtitle_parts = []
        if domain:
            subtitle_parts.append(f"Domain: {domain}")
        else:
            subtitle_parts.append("All Domains")

        if start_date and end_date:
            subtitle_parts.append(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        elif days:
            subtitle_parts.append(f"Last {days} days")

        subtitle_parts.append(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

        story.append(Paragraph("<br/>".join(subtitle_parts), self.styles['CustomSubtitle']))
        story.append(Spacer(1, 0.5*inch))

        # Executive Summary
        story.append(Paragraph("Executive Summary", self.styles['SectionHeading']))
        summary_data = self._get_summary_data(domain, days, start_date, end_date)
        story.append(self._create_summary_table(summary_data))
        story.append(Spacer(1, 0.3*inch))

        # Compliance Chart
        story.append(Paragraph("Policy Compliance", self.styles['SectionHeading']))
        alignment_data = self._get_alignment_data(domain, days, start_date, end_date)
        story.append(self._create_compliance_chart(alignment_data))
        story.append(Spacer(1, 0.3*inch))

        # Authentication Alignment Breakdown
        story.append(Paragraph("Authentication Alignment Breakdown", self.styles['SectionHeading']))
        story.append(self._create_alignment_table(alignment_data))
        story.append(Spacer(1, 0.3*inch))

        # Top Source IPs
        story.append(Paragraph("Top Source IPs", self.styles['SectionHeading']))
        sources_data = self._get_top_sources(domain, days, start_date, end_date, limit=10)
        story.append(self._create_sources_table(sources_data))

        # Build PDF
        doc.build(story)

        # Get PDF bytes
        buffer.seek(0)
        return buffer.getvalue()

    def _get_summary_data(
        self,
        domain: Optional[str],
        days: Optional[int],
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> dict:
        """Get executive summary statistics"""
        query = self.db.query(
            func.count(func.distinct(DmarcReport.id)).label('total_reports'),
            func.sum(DmarcRecord.count).label('total_messages'),
            func.sum(
                case(
                    (and_(DmarcRecord.dkim_result == 'pass', DmarcRecord.spf_result == 'pass'),
                         DmarcRecord.count),
                    else_=0
                )
            ).label('pass_count'),
            func.sum(
                case(
                    (and_(DmarcRecord.dkim_result != 'pass', DmarcRecord.spf_result != 'pass'),
                         DmarcRecord.count),
                    else_=0
                )
            ).label('fail_count')
        ).join(
            DmarcRecord, DmarcReport.id == DmarcRecord.report_id
        )

        query = self._apply_filters(query, domain, days, start_date, end_date)

        result = query.one()

        total_messages = result.total_messages or 0
        pass_count = result.pass_count or 0
        fail_count = result.fail_count or 0

        return {
            'total_reports': result.total_reports or 0,
            'total_messages': total_messages,
            'pass_count': pass_count,
            'fail_count': fail_count,
            'pass_rate': (pass_count / total_messages * 100) if total_messages > 0 else 0,
            'fail_rate': (fail_count / total_messages * 100) if total_messages > 0 else 0
        }

    def _get_alignment_data(
        self,
        domain: Optional[str],
        days: Optional[int],
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> dict:
        """Get authentication alignment statistics"""
        query = self.db.query(
            func.sum(
                case(
                    (and_(DmarcRecord.dkim_result == 'pass', DmarcRecord.spf_result == 'pass'),
                         DmarcRecord.count),
                    else_=0
                )
            ).label('both_pass'),
            func.sum(
                case(
                    (and_(DmarcRecord.dkim_result == 'pass', DmarcRecord.spf_result != 'pass'),
                         DmarcRecord.count),
                    else_=0
                )
            ).label('dkim_only'),
            func.sum(
                case(
                    (and_(DmarcRecord.dkim_result != 'pass', DmarcRecord.spf_result == 'pass'),
                         DmarcRecord.count),
                    else_=0
                )
            ).label('spf_only'),
            func.sum(
                case(
                    (and_(DmarcRecord.dkim_result != 'pass', DmarcRecord.spf_result != 'pass'),
                         DmarcRecord.count),
                    else_=0
                )
            ).label('both_fail')
        ).join(
            DmarcReport, DmarcRecord.report_id == DmarcReport.id
        )

        query = self._apply_filters(query, domain, days, start_date, end_date)

        result = query.one()

        return {
            'both_pass': result.both_pass or 0,
            'dkim_only': result.dkim_only or 0,
            'spf_only': result.spf_only or 0,
            'both_fail': result.both_fail or 0
        }

    def _get_top_sources(
        self,
        domain: Optional[str],
        days: Optional[int],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        limit: int = 10
    ) -> list:
        """Get top source IPs"""
        query = self.db.query(
            DmarcRecord.source_ip,
            func.sum(DmarcRecord.count).label('total_messages'),
            func.sum(
                case(
                    (and_(DmarcRecord.dkim_result == 'pass', DmarcRecord.spf_result == 'pass'),
                         DmarcRecord.count),
                    else_=0
                )
            ).label('pass_count'),
            func.sum(
                case(
                    (and_(DmarcRecord.dkim_result != 'pass', DmarcRecord.spf_result != 'pass'),
                         DmarcRecord.count),
                    else_=0
                )
            ).label('fail_count')
        ).join(
            DmarcReport, DmarcRecord.report_id == DmarcReport.id
        )

        query = self._apply_filters(query, domain, days, start_date, end_date)

        query = query.group_by(DmarcRecord.source_ip).order_by(
            func.sum(DmarcRecord.count).desc()
        ).limit(limit)

        return query.all()

    def _create_summary_table(self, data: dict) -> Table:
        """Create executive summary table"""
        table_data = [
            ['Metric', 'Value'],
            ['Total Reports', f"{data['total_reports']:,}"],
            ['Total Messages', f"{data['total_messages']:,}"],
            ['Pass Count', f"{data['pass_count']:,}"],
            ['Fail Count', f"{data['fail_count']:,}"],
            ['Pass Rate', f"{data['pass_rate']:.2f}%"],
            ['Fail Rate', f"{data['fail_rate']:.2f}%"]
        ]

        table = Table(table_data, colWidths=[3*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ]))

        return table

    def _create_compliance_chart(self, data: dict) -> Drawing:
        """Create compliance pie chart"""
        drawing = Drawing(400, 200)

        compliant = data['both_pass']
        non_compliant = data['dkim_only'] + data['spf_only'] + data['both_fail']
        total = compliant + non_compliant

        if total == 0:
            # Empty chart
            compliant = 1
            non_compliant = 0
            labels = ['No Data']
        else:
            labels = [
                f'Compliant: {compliant:,} ({compliant/total*100:.1f}%)',
                f'Non-Compliant: {non_compliant:,} ({non_compliant/total*100:.1f}%)'
            ]

        pie = Pie()
        pie.x = 150
        pie.y = 50
        pie.width = 120
        pie.height = 120
        pie.data = [compliant, non_compliant]
        pie.labels = labels
        pie.slices.strokeWidth = 0.5
        pie.slices[0].fillColor = colors.HexColor('#27ae60')
        pie.slices[1].fillColor = colors.HexColor('#e74c3c')

        drawing.add(pie)
        return drawing

    def _create_alignment_table(self, data: dict) -> Table:
        """Create authentication alignment breakdown table"""
        total = data['both_pass'] + data['dkim_only'] + data['spf_only'] + data['both_fail']

        table_data = [
            ['Authentication Status', 'Message Count', 'Percentage'],
            [
                'Both Pass',
                f"{data['both_pass']:,}",
                f"{(data['both_pass']/total*100) if total > 0 else 0:.2f}%"
            ],
            [
                'DKIM Only',
                f"{data['dkim_only']:,}",
                f"{(data['dkim_only']/total*100) if total > 0 else 0:.2f}%"
            ],
            [
                'SPF Only',
                f"{data['spf_only']:,}",
                f"{(data['spf_only']/total*100) if total > 0 else 0:.2f}%"
            ],
            [
                'Both Fail',
                f"{data['both_fail']:,}",
                f"{(data['both_fail']/total*100) if total > 0 else 0:.2f}%"
            ]
        ]

        table = Table(table_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (1, 1), (2, -1), 'RIGHT'),
        ]))

        return table

    def _create_sources_table(self, sources: list) -> Table:
        """Create top sources table"""
        table_data = [['Source IP', 'Total Messages', 'Pass Count', 'Fail Count', 'Pass %']]

        for source in sources:
            total = source.total_messages or 0
            pass_count = source.pass_count or 0
            fail_count = source.fail_count or 0
            pass_pct = (pass_count / total * 100) if total > 0 else 0

            table_data.append([
                source.source_ip,
                f"{total:,}",
                f"{pass_count:,}",
                f"{fail_count:,}",
                f"{pass_pct:.1f}%"
            ])

        if len(table_data) == 1:
            table_data.append(['No data', '-', '-', '-', '-'])

        table = Table(table_data, colWidths=[2*inch, 1.2*inch, 1.2*inch, 1.2*inch, 0.9*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ]))

        return table

    def _apply_filters(
        self,
        query,
        domain: Optional[str],
        days: Optional[int],
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ):
        """Apply common filters to query"""
        if domain:
            query = query.filter(DmarcReport.domain == domain)

        if start_date and end_date:
            query = query.filter(
                and_(
                    DmarcReport.date_end >= start_date,
                    DmarcReport.date_end <= end_date
                )
            )
        elif days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(DmarcReport.date_end >= cutoff)

        return query
