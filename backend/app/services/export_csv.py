"""
CSV Export Service

Provides CSV export functionality for DMARC reports, records, and source statistics
"""
import csv
import io
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case

from app.models import DmarcReport, DmarcRecord


class CSVExportService:
    """Service for exporting DMARC data to CSV format"""

    def __init__(self, db: Session):
        self.db = db

    def export_reports(
        self,
        domain: Optional[str] = None,
        days: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        org_name: Optional[str] = None
    ) -> str:
        """
        Export DMARC reports to CSV

        Args:
            domain: Filter by domain
            days: Number of days to include
            start_date: Start date for filtering
            end_date: End date for filtering
            org_name: Filter by organization name

        Returns:
            CSV string
        """
        # Build query
        query = self.db.query(
            DmarcReport.report_id,
            DmarcReport.org_name,
            DmarcReport.email,
            DmarcReport.domain,
            DmarcReport.date_begin,
            DmarcReport.date_end,
            DmarcReport.p,
            DmarcReport.sp,
            DmarcReport.pct,
            DmarcReport.adkim,
            DmarcReport.aspf,
            func.count(DmarcRecord.id).label('record_count'),
            func.sum(DmarcRecord.count).label('total_messages')
        ).outerjoin(
            DmarcRecord, DmarcReport.id == DmarcRecord.report_id
        )

        # Apply filters
        query = self._apply_filters(query, domain, days, start_date, end_date, org_name)

        query = query.group_by(
            DmarcReport.id,
            DmarcReport.report_id,
            DmarcReport.org_name,
            DmarcReport.email,
            DmarcReport.domain,
            DmarcReport.date_begin,
            DmarcReport.date_end,
            DmarcReport.p,
            DmarcReport.sp,
            DmarcReport.pct,
            DmarcReport.adkim,
            DmarcReport.aspf
        )

        results = query.all()

        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Report ID',
            'Organization',
            'Email',
            'Domain',
            'Date Begin',
            'Date End',
            'Policy (p)',
            'Subdomain Policy (sp)',
            'Percentage (pct)',
            'DKIM Alignment',
            'SPF Alignment',
            'Record Count',
            'Total Messages'
        ])

        # Data rows
        for row in results:
            writer.writerow([
                self._escape_csv(row.report_id),
                self._escape_csv(row.org_name),
                self._escape_csv(row.email),
                self._escape_csv(row.domain),
                row.date_begin.isoformat() if row.date_begin else '',
                row.date_end.isoformat() if row.date_end else '',
                row.p or '',
                row.sp or '',
                row.pct or '',
                row.adkim or '',
                row.aspf or '',
                row.record_count or 0,
                row.total_messages or 0
            ])

        return output.getvalue()

    def export_records(
        self,
        domain: Optional[str] = None,
        days: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        source_ip: Optional[str] = None,
        dkim_result: Optional[str] = None,
        spf_result: Optional[str] = None,
        disposition: Optional[str] = None,
        org_name: Optional[str] = None,
        limit: int = 10000
    ) -> str:
        """
        Export DMARC records to CSV with full details

        Args:
            domain: Filter by domain
            days: Number of days to include
            start_date: Start date for filtering
            end_date: End date for filtering
            source_ip: Filter by source IP
            dkim_result: Filter by DKIM result
            spf_result: Filter by SPF result
            disposition: Filter by disposition
            org_name: Filter by organization name
            limit: Maximum number of records (default: 10000)

        Returns:
            CSV string
        """
        # Build query
        query = self.db.query(
            DmarcReport.report_id,
            DmarcReport.org_name,
            DmarcReport.domain,
            DmarcReport.date_begin,
            DmarcReport.date_end,
            DmarcRecord.source_ip,
            DmarcRecord.count,
            DmarcRecord.disposition,
            DmarcRecord.dkim,
            DmarcRecord.spf,
            DmarcRecord.header_from,
            DmarcRecord.envelope_from,
            DmarcRecord.envelope_to,
            DmarcRecord.dkim_domain,
            DmarcRecord.dkim_result,
            DmarcRecord.dkim_selector,
            DmarcRecord.spf_domain,
            DmarcRecord.spf_result,
            DmarcRecord.spf_scope
        ).join(
            DmarcReport, DmarcRecord.report_id == DmarcReport.id
        )

        # Apply filters
        query = self._apply_filters(query, domain, days, start_date, end_date, org_name)

        # Apply record-specific filters
        if source_ip:
            query = query.filter(DmarcRecord.source_ip == source_ip)

        if dkim_result:
            query = query.filter(DmarcRecord.dkim_result == dkim_result)

        if spf_result:
            query = query.filter(DmarcRecord.spf_result == spf_result)

        if disposition:
            query = query.filter(DmarcRecord.disposition == disposition)

        query = query.limit(limit)
        results = query.all()

        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Report ID',
            'Organization',
            'Domain',
            'Report Date Begin',
            'Report Date End',
            'Source IP',
            'Message Count',
            'Disposition',
            'DKIM Policy',
            'SPF Policy',
            'Header From',
            'Envelope From',
            'Envelope To',
            'DKIM Domain',
            'DKIM Result',
            'DKIM Selector',
            'SPF Domain',
            'SPF Result',
            'SPF Scope'
        ])

        # Data rows
        for row in results:
            writer.writerow([
                self._escape_csv(row.report_id),
                self._escape_csv(row.org_name),
                self._escape_csv(row.domain),
                row.date_begin.isoformat() if row.date_begin else '',
                row.date_end.isoformat() if row.date_end else '',
                self._escape_csv(row.source_ip),
                row.count or 0,
                self._escape_csv(row.disposition),
                self._escape_csv(row.dkim),
                self._escape_csv(row.spf),
                self._escape_csv(row.header_from),
                self._escape_csv(row.envelope_from),
                self._escape_csv(row.envelope_to),
                self._escape_csv(row.dkim_domain),
                self._escape_csv(row.dkim_result),
                self._escape_csv(row.dkim_selector),
                self._escape_csv(row.spf_domain),
                self._escape_csv(row.spf_result),
                self._escape_csv(row.spf_scope)
            ])

        return output.getvalue()

    def export_sources(
        self,
        domain: Optional[str] = None,
        days: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        org_name: Optional[str] = None,
        limit: int = 1000
    ) -> str:
        """
        Export aggregated source IP statistics to CSV

        Args:
            domain: Filter by domain
            days: Number of days to include
            start_date: Start date for filtering
            end_date: End date for filtering
            org_name: Filter by organization name
            limit: Maximum number of sources (default: 1000)

        Returns:
            CSV string
        """
        # Build aggregation query
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

        # Apply filters
        query = self._apply_filters(query, domain, days, start_date, end_date, org_name)

        query = query.group_by(DmarcRecord.source_ip).order_by(
            func.sum(DmarcRecord.count).desc()
        ).limit(limit)

        results = query.all()

        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Source IP',
            'Total Messages',
            'Pass Count',
            'Fail Count',
            'Pass Percentage'
        ])

        # Data rows
        for row in results:
            total = row.total_messages or 0
            pass_count = row.pass_count or 0
            fail_count = row.fail_count or 0
            pass_pct = (pass_count / total * 100) if total > 0 else 0

            writer.writerow([
                self._escape_csv(row.source_ip),
                total,
                pass_count,
                fail_count,
                f"{pass_pct:.2f}%"
            ])

        return output.getvalue()

    def _apply_filters(
        self,
        query,
        domain: Optional[str],
        days: Optional[int],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        org_name: Optional[str]
    ):
        """Apply common filters to query"""
        if domain:
            query = query.filter(DmarcReport.domain == domain)

        if org_name:
            query = query.filter(DmarcReport.org_name.ilike(f'%{org_name}%'))

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

    def _escape_csv(self, value: Optional[str]) -> str:
        """
        Escape CSV values to prevent formula injection and handle None

        Args:
            value: Value to escape

        Returns:
            Escaped string
        """
        if value is None:
            return ''

        value_str = str(value)

        # Prevent CSV injection (formula injection)
        # If value starts with special characters, prefix with single quote
        if value_str and value_str[0] in ['=', '+', '-', '@', '\t', '\r']:
            value_str = "'" + value_str

        return value_str
