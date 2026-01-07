"""
Report Processing Service

Connects ingestion and parsing by:
1. Reading pending reports from ingested_reports table
2. Parsing them using the DMARC parser
3. Saving parsed data to dmarc_reports and dmarc_records tables
4. Updating ingested_reports status
"""
import logging
from pathlib import Path
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Tuple

from app.models import IngestedReport, DmarcReport, DmarcRecord
from app.parsers.dmarc_parser import parse_dmarc_report, DmarcParseError

logger = logging.getLogger(__name__)


class ReportProcessor:
    """Process ingested DMARC reports"""

    def __init__(self, db: Session, storage_base_path: str):
        """
        Initialize processor

        Args:
            db: Database session
            storage_base_path: Base path where raw reports are stored
        """
        self.db = db
        self.storage_base_path = Path(storage_base_path)

    def process_pending_reports(self, limit: int = 100) -> Tuple[int, int]:
        """
        Process pending reports from the ingested_reports table

        Args:
            limit: Maximum number of reports to process in one batch

        Returns:
            Tuple of (processed_count, failed_count)
        """
        # Find pending reports
        pending_reports = self.db.query(IngestedReport).filter(
            IngestedReport.status == 'pending'
        ).limit(limit).all()

        processed_count = 0
        failed_count = 0

        for ingested_report in pending_reports:
            try:
                self._process_single_report(ingested_report)
                processed_count += 1
                logger.info(
                    f"Successfully processed report {ingested_report.id} "
                    f"(filename: {ingested_report.filename})"
                )
            except Exception as e:
                failed_count += 1
                logger.error(
                    f"Failed to process report {ingested_report.id} "
                    f"(filename: {ingested_report.filename}): {str(e)}",
                    exc_info=True
                )
                # Update status to failed
                ingested_report.status = 'failed'
                ingested_report.parse_error = str(e)
                ingested_report.updated_at = datetime.utcnow()

        # Commit all changes
        self.db.commit()

        # Invalidate caches after successful processing
        if processed_count > 0:
            from app.services.cache import get_cache
            cache = get_cache()
            cache.invalidate_pattern("timeline:*")
            cache.invalidate_pattern("summary:*")
            cache.invalidate_pattern("sources:*")
            cache.invalidate_pattern("domains:*")
            cache.invalidate_pattern("alignment:*")
            logger.info("Cache invalidated after processing reports")

        logger.info(
            f"Batch processing complete: {processed_count} processed, "
            f"{failed_count} failed"
        )

        return processed_count, failed_count

    def _process_single_report(self, ingested_report: IngestedReport):
        """
        Process a single ingested report

        Args:
            ingested_report: IngestedReport record to process

        Raises:
            DmarcParseError: If parsing fails
            Exception: For other errors
        """
        # Update status to processing
        ingested_report.status = 'processing'
        ingested_report.updated_at = datetime.utcnow()
        self.db.flush()

        # Read the raw file
        file_path = self.storage_base_path / ingested_report.storage_path
        if not file_path.exists():
            raise FileNotFoundError(
                f"Raw file not found: {ingested_report.storage_path}"
            )

        with open(file_path, 'rb') as f:
            file_content = f.read()

        # Parse the report
        try:
            parsed_report = parse_dmarc_report(
                file_content,
                ingested_report.filename
            )
        except DmarcParseError as e:
            raise DmarcParseError(f"Failed to parse DMARC XML: {str(e)}")

        # Check if this report already exists (by report_id)
        existing_report = self.db.query(DmarcReport).filter(
            DmarcReport.report_id == parsed_report.metadata.report_id
        ).first()

        if existing_report:
            logger.warning(
                f"Report with report_id {parsed_report.metadata.report_id} "
                f"already exists in database. Skipping."
            )
            # Mark as completed even though we skipped it
            ingested_report.status = 'completed'
            ingested_report.updated_at = datetime.utcnow()
            return

        # Create DmarcReport record
        dmarc_report = DmarcReport(
            ingested_report_id=ingested_report.id,
            report_id=parsed_report.metadata.report_id,
            org_name=parsed_report.metadata.org_name,
            email=parsed_report.metadata.email,
            extra_contact_info=parsed_report.metadata.extra_contact_info,
            date_begin=parsed_report.metadata.date_begin,
            date_end=parsed_report.metadata.date_end,
            domain=parsed_report.policy_published.domain,
            adkim=parsed_report.policy_published.adkim,
            aspf=parsed_report.policy_published.aspf,
            p=parsed_report.policy_published.p,
            sp=parsed_report.policy_published.sp,
            pct=parsed_report.policy_published.pct
        )

        self.db.add(dmarc_report)
        self.db.flush()  # Get the ID

        # Create DmarcRecord records
        for record in parsed_report.records:
            # Get first DKIM and SPF results (if available)
            dkim_result = record.auth_results_dkim[0] if record.auth_results_dkim else None
            spf_result = record.auth_results_spf[0] if record.auth_results_spf else None

            dmarc_record = DmarcRecord(
                report_id=dmarc_report.id,
                source_ip=record.source_ip,
                count=record.count,
                disposition=record.policy_evaluated.disposition,
                dkim=record.policy_evaluated.dkim,
                spf=record.policy_evaluated.spf,
                header_from=record.identifiers.header_from,
                envelope_from=record.identifiers.envelope_from,
                envelope_to=record.identifiers.envelope_to,
                dkim_domain=dkim_result.domain if dkim_result else None,
                dkim_result=dkim_result.result if dkim_result else None,
                dkim_selector=dkim_result.selector if dkim_result else None,
                spf_domain=spf_result.domain if spf_result else None,
                spf_result=spf_result.result if spf_result else None,
                spf_scope=spf_result.scope if spf_result else None
            )
            self.db.add(dmarc_record)

        # Update ingested report status
        ingested_report.status = 'completed'
        ingested_report.updated_at = datetime.utcnow()

        logger.debug(
            f"Created DmarcReport {dmarc_report.id} with "
            f"{len(parsed_report.records)} records"
        )

    def reprocess_failed_reports(self, limit: int = 50) -> Tuple[int, int]:
        """
        Retry processing failed reports

        Args:
            limit: Maximum number of failed reports to retry

        Returns:
            Tuple of (processed_count, failed_count)
        """
        failed_reports = self.db.query(IngestedReport).filter(
            IngestedReport.status == 'failed'
        ).limit(limit).all()

        processed_count = 0
        still_failed_count = 0

        for ingested_report in failed_reports:
            # Reset status to pending
            ingested_report.status = 'pending'
            ingested_report.parse_error = None
            ingested_report.updated_at = datetime.utcnow()

        self.db.commit()

        # Process them
        return self.process_pending_reports(limit)
