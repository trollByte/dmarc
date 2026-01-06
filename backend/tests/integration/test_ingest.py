import pytest
from unittest.mock import Mock, MagicMock
from email.message import Message
import gzip
from app.ingest.processor import IngestProcessor
from app.ingest.email_client import EmailClient
from app.models import ProcessedEmail, Report, Record


class MockEmailClient:
    """Mock email client for testing"""

    def __init__(self, emails_data):
        """
        Initialize mock client

        Args:
            emails_data: List of tuples (email_id, message_id, subject, attachments)
                         attachments: List of tuples (filename, data)
        """
        self.emails_data = emails_data
        self.connected = False

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False

    def search_dmarc_reports(self, limit=50):
        return [str(i) for i in range(len(self.emails_data))]

    def fetch_email(self, email_id: str) -> Message:
        idx = int(email_id)
        email_data = self.emails_data[idx]

        msg = Message()
        msg['Message-ID'] = email_data[1]
        msg['Subject'] = email_data[2]

        # Add attachments as parts
        for filename, data in email_data[3]:
            part = Message()
            part.set_payload(data)
            part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
            part.set_type('application/octet-stream')
            msg.attach(part)

        return msg

    def get_message_id(self, msg: Message) -> str:
        return msg.get('Message-ID', '')

    def get_subject(self, msg: Message) -> str:
        return msg.get('Subject', '')

    def get_attachments(self, msg: Message):
        attachments = []
        if hasattr(msg, '_payload') and isinstance(msg._payload, list):
            for part in msg._payload:
                filename = None
                content_disp = part.get('Content-Disposition', '')
                if 'filename=' in content_disp:
                    filename = content_disp.split('filename=')[1].strip('"')

                if filename:
                    data = part.get_payload()
                    if isinstance(data, str):
                        data = data.encode()
                    attachments.append((filename, data))

        return attachments

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


class TestIngestIntegration:
    """Integration tests for the complete ingest pipeline"""

    def test_ingest_single_report(self, db_session, sample_xml):
        """Test ingesting a single DMARC report"""
        # Create mock email client with one email
        emails = [
            ('1', '<msg-001@example.com>', 'DMARC Report', [
                ('report.xml', sample_xml)
            ])
        ]
        mock_client = MockEmailClient(emails)

        # Create processor
        processor = IngestProcessor(db_session, mock_client)

        # Run ingest
        emails_checked, reports_processed = processor.run()

        # Verify results
        assert emails_checked == 1
        assert reports_processed == 1

        # Verify email marked as processed
        processed = db_session.query(ProcessedEmail).filter_by(
            message_id='<msg-001@example.com>'
        ).first()
        assert processed is not None
        assert processed.subject == 'DMARC Report'

        # Verify report saved
        report = db_session.query(Report).filter_by(
            report_id='12345678901234567890'
        ).first()
        assert report is not None
        assert report.org_name == 'Google Inc.'
        assert report.domain == 'example.com'

        # Verify records saved
        records = db_session.query(Record).filter_by(report_id=report.id).all()
        assert len(records) == 2
        assert records[0].source_ip == '192.0.2.1'
        assert records[0].count == 5
        assert records[1].source_ip == '203.0.113.5'
        assert records[1].count == 2

    def test_ingest_idempotency(self, db_session, sample_xml):
        """Test that running ingest twice doesn't create duplicates"""
        # Create mock email client
        emails = [
            ('1', '<msg-002@example.com>', 'DMARC Report', [
                ('report.xml', sample_xml)
            ])
        ]
        mock_client = MockEmailClient(emails)

        # Create processor
        processor = IngestProcessor(db_session, mock_client)

        # Run ingest first time
        emails_checked, reports_processed = processor.run()
        assert emails_checked == 1
        assert reports_processed == 1

        # Verify counts
        initial_email_count = db_session.query(ProcessedEmail).count()
        initial_report_count = db_session.query(Report).count()
        initial_record_count = db_session.query(Record).count()

        assert initial_email_count == 1
        assert initial_report_count == 1
        assert initial_record_count == 2

        # Create new mock client with same data
        mock_client2 = MockEmailClient(emails)
        processor2 = IngestProcessor(db_session, mock_client2)

        # Run ingest second time (should skip duplicate)
        emails_checked2, reports_processed2 = processor2.run()
        assert emails_checked2 == 1
        assert reports_processed2 == 0  # No new reports

        # Verify counts haven't changed
        final_email_count = db_session.query(ProcessedEmail).count()
        final_report_count = db_session.query(Report).count()
        final_record_count = db_session.query(Record).count()

        assert final_email_count == initial_email_count
        assert final_report_count == initial_report_count
        assert final_record_count == initial_record_count

    def test_ingest_multiple_reports(self, db_session, sample_xml):
        """Test ingesting multiple reports from multiple emails"""
        # Create second sample report with different report_id
        sample_xml2 = sample_xml.replace(
            b'<report_id>12345678901234567890</report_id>',
            b'<report_id>99999999999999999999</report_id>'
        )
        sample_xml2 = sample_xml2.replace(
            b'<org_name>Google Inc.</org_name>',
            b'<org_name>Microsoft Corporation</org_name>'
        )

        # Create mock email client with multiple emails
        emails = [
            ('1', '<msg-003@example.com>', 'DMARC Report 1', [
                ('report1.xml.gz', gzip.compress(sample_xml))
            ]),
            ('2', '<msg-004@example.com>', 'DMARC Report 2', [
                ('report2.xml', sample_xml2)
            ])
        ]
        mock_client = MockEmailClient(emails)

        # Create processor
        processor = IngestProcessor(db_session, mock_client)

        # Run ingest
        emails_checked, reports_processed = processor.run()

        # Verify results
        assert emails_checked == 2
        assert reports_processed == 2

        # Verify both emails marked as processed
        assert db_session.query(ProcessedEmail).count() == 2

        # Verify both reports saved
        reports = db_session.query(Report).all()
        assert len(reports) == 2

        org_names = {r.org_name for r in reports}
        assert 'Google Inc.' in org_names
        assert 'Microsoft Corporation' in org_names

        # Verify all records saved (2 records per report = 4 total)
        assert db_session.query(Record).count() == 4

    def test_ingest_skip_invalid_attachment(self, db_session, malformed_xml):
        """Test that invalid attachments are skipped gracefully"""
        # Create mock email with invalid attachment
        emails = [
            ('1', '<msg-005@example.com>', 'DMARC Report', [
                ('invalid.xml', malformed_xml)
            ])
        ]
        mock_client = MockEmailClient(emails)

        # Create processor
        processor = IngestProcessor(db_session, mock_client)

        # Run ingest (should not crash)
        emails_checked, reports_processed = processor.run()

        # Verify results
        assert emails_checked == 1
        assert reports_processed == 0  # Invalid report not processed

        # Email should still be marked as processed
        processed = db_session.query(ProcessedEmail).filter_by(
            message_id='<msg-005@example.com>'
        ).first()
        assert processed is not None

        # No reports should be saved
        assert db_session.query(Report).count() == 0

    def test_ingest_email_without_attachments(self, db_session):
        """Test processing email without attachments"""
        # Create mock email without attachments
        emails = [
            ('1', '<msg-006@example.com>', 'DMARC Report', [])
        ]
        mock_client = MockEmailClient(emails)

        # Create processor
        processor = IngestProcessor(db_session, mock_client)

        # Run ingest
        emails_checked, reports_processed = processor.run()

        # Verify results
        assert emails_checked == 1
        assert reports_processed == 0

        # Email should be marked as processed
        processed = db_session.query(ProcessedEmail).filter_by(
            message_id='<msg-006@example.com>'
        ).first()
        assert processed is not None

    def test_ingest_duplicate_report_different_email(self, db_session, sample_xml):
        """Test that duplicate report_id from different email is skipped"""
        # Create two emails with same report but different message IDs
        emails = [
            ('1', '<msg-007@example.com>', 'DMARC Report 1', [
                ('report1.xml', sample_xml)
            ]),
            ('2', '<msg-008@example.com>', 'DMARC Report 2', [
                ('report2.xml', sample_xml)
            ])
        ]
        mock_client = MockEmailClient(emails)

        # Create processor
        processor = IngestProcessor(db_session, mock_client)

        # Run ingest
        emails_checked, reports_processed = processor.run()

        # Verify results
        assert emails_checked == 2
        assert reports_processed == 1  # Only first report saved

        # Both emails should be marked as processed
        assert db_session.query(ProcessedEmail).count() == 2

        # Only one report should exist
        reports = db_session.query(Report).all()
        assert len(reports) == 1
        assert reports[0].report_id == '12345678901234567890'

        # Only one set of records (2 records)
        assert db_session.query(Record).count() == 2
