from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Tuple
from app.ingest.email_client import EmailClient
from app.ingest.parser import parse_dmarc_report
from app.models import ProcessedEmail, Report, Record
from app.schemas import ReportCreate
import logging

logger = logging.getLogger(__name__)


class IngestProcessor:
    """Processes DMARC reports from email inbox"""

    def __init__(self, db: Session, email_client: EmailClient = None):
        """
        Initialize processor

        Args:
            db: Database session
            email_client: Optional email client (for testing)
        """
        self.db = db
        self.email_client = email_client

    def is_email_processed(self, message_id: str) -> bool:
        """
        Check if email has already been processed

        Args:
            message_id: Email message ID

        Returns:
            True if already processed
        """
        return self.db.query(ProcessedEmail).filter(
            ProcessedEmail.message_id == message_id
        ).first() is not None

    def mark_email_processed(self, message_id: str, subject: str = None):
        """
        Mark email as processed

        Args:
            message_id: Email message ID
            subject: Email subject
        """
        processed = ProcessedEmail(
            message_id=message_id,
            subject=subject
        )
        self.db.add(processed)
        self.db.commit()

    def is_report_exists(self, report_id: str) -> bool:
        """
        Check if report already exists in database

        Args:
            report_id: DMARC report ID

        Returns:
            True if report exists
        """
        return self.db.query(Report).filter(
            Report.report_id == report_id
        ).first() is not None

    def save_report(self, report_data: ReportCreate) -> Report:
        """
        Save parsed report to database

        Args:
            report_data: Parsed report data

        Returns:
            Saved report object
        """
        # Check if report already exists
        if self.is_report_exists(report_data.report_id):
            logger.info(f"Report {report_data.report_id} already exists, skipping")
            return None

        # Create report
        report = Report(
            report_id=report_data.report_id,
            org_name=report_data.org_name,
            email=report_data.email,
            extra_contact_info=report_data.extra_contact_info,
            date_begin=report_data.date_begin,
            date_end=report_data.date_end,
            domain=report_data.domain,
            adkim=report_data.adkim,
            aspf=report_data.aspf,
            p=report_data.p,
            sp=report_data.sp,
            pct=report_data.pct
        )

        self.db.add(report)
        self.db.flush()  # Get report.id

        # Create records
        for record_data in report_data.records:
            record = Record(
                report_id=report.id,
                source_ip=record_data.source_ip,
                count=record_data.count,
                disposition=record_data.disposition,
                dkim_result=record_data.dkim_result,
                spf_result=record_data.spf_result,
                envelope_to=record_data.envelope_to,
                envelope_from=record_data.envelope_from,
                header_from=record_data.header_from,
                dkim_domain=record_data.dkim_domain,
                dkim_selector=record_data.dkim_selector,
                dkim_auth_result=record_data.dkim_auth_result,
                spf_domain=record_data.spf_domain,
                spf_scope=record_data.spf_scope,
                spf_auth_result=record_data.spf_auth_result
            )
            self.db.add(record)

        self.db.commit()
        logger.info(f"Saved report {report_data.report_id} with {len(report_data.records)} records")

        return report

    def process_attachment(self, filename: str, data: bytes) -> ReportCreate:
        """
        Process a single attachment

        Args:
            filename: Attachment filename
            data: Attachment data

        Returns:
            Parsed report data or None if parsing fails
        """
        try:
            return parse_dmarc_report(data, filename)
        except Exception as e:
            logger.error(f"Failed to parse attachment {filename}: {str(e)}")
            return None

    def process_email(self, email_id: str) -> int:
        """
        Process a single email

        Args:
            email_id: Email UID

        Returns:
            Number of reports processed
        """
        if not self.email_client:
            raise RuntimeError("Email client not initialized")

        # Fetch email
        msg = self.email_client.fetch_email(email_id)
        message_id = self.email_client.get_message_id(msg)
        subject = self.email_client.get_subject(msg)

        # Check if already processed (idempotency)
        if self.is_email_processed(message_id):
            logger.info(f"Email {message_id} already processed, skipping")
            return 0

        # Get attachments
        attachments = self.email_client.get_attachments(msg)

        if not attachments:
            logger.warning(f"No attachments found in email {message_id}")
            self.mark_email_processed(message_id, subject)
            return 0

        reports_saved = 0

        # Process each attachment
        for filename, data in attachments:
            report_data = self.process_attachment(filename, data)

            if report_data:
                saved_report = self.save_report(report_data)
                if saved_report:
                    reports_saved += 1

        # Mark email as processed
        self.mark_email_processed(message_id, subject)

        return reports_saved

    def run(self, limit: int = 50) -> Tuple[int, int]:
        """
        Run the ingest process

        Args:
            limit: Maximum number of emails to process

        Returns:
            Tuple of (emails_checked, reports_processed)
        """
        if not self.email_client:
            # Create email client if not provided
            self.email_client = EmailClient()

        emails_checked = 0
        reports_processed = 0

        try:
            with self.email_client:
                # Search for DMARC report emails
                email_ids = self.email_client.search_dmarc_reports(limit)
                emails_checked = len(email_ids)

                logger.info(f"Found {emails_checked} potential DMARC report emails")

                # Process each email
                for email_id in email_ids:
                    try:
                        count = self.process_email(email_id)
                        reports_processed += count
                    except Exception as e:
                        logger.error(f"Error processing email {email_id}: {str(e)}")
                        continue

        except Exception as e:
            logger.error(f"Ingest process failed: {str(e)}")
            raise

        logger.info(f"Ingest complete: {reports_processed} reports from {emails_checked} emails")

        return emails_checked, reports_processed
