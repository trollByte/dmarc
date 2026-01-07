import pytest
from unittest.mock import Mock
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime

from app.services.ingestion import IngestionService
from app.services.storage import StorageService
from app.models import IngestedReport


class MockIMAPClient:
    """Mock IMAP client for testing"""

    def __init__(self, messages_data):
        """
        Initialize with test data

        Args:
            messages_data: List of tuples (message_id, subject, date, attachments)
                          attachments: List of tuples (filename, content)
        """
        self.messages_data = messages_data
        self.connected = False

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False

    def search_messages(self, criteria, limit):
        """Return mock message IDs"""
        return [str(i).encode() for i in range(len(self.messages_data))]

    def fetch_message(self, message_id):
        """Return mock message"""
        idx = int(message_id)
        msg_data = self.messages_data[idx]

        msg = MIMEMultipart()
        msg['Message-ID'] = msg_data[0]
        msg['Subject'] = msg_data[1]
        msg['Date'] = msg_data[2]

        # Add attachments
        for filename, content in msg_data[3]:
            part = MIMEApplication(content)
            part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
            msg.attach(part)

        return msg

    def get_message_id(self, msg):
        return msg.get('Message-ID', '')

    def get_subject(self, msg):
        return msg.get('Subject', '')

    def get_date(self, msg):
        date_str = msg.get('Date', '')
        try:
            import email.utils
            return email.utils.parsedate_to_datetime(date_str)
        except:
            return datetime.utcnow()

    def get_attachments(self, msg):
        """Extract attachments from mock message"""
        attachments = []

        if hasattr(msg, '_payload') and isinstance(msg._payload, list):
            for part in msg._payload:
                if part.get_content_type() == 'application/octet-stream':
                    filename = part.get_filename()
                    content = part.get_payload(decode=True)
                    if filename and content:
                        # Filter by extension
                        if any(filename.lower().endswith(ext) for ext in ['.xml', '.gz', '.zip']):
                            attachments.append((filename, content))

        return attachments

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


class TestIngestionService:
    """Integration tests for ingestion service"""

    def test_ingest_single_report(self, db_session, temp_storage, sample_xml):
        """Test ingesting a single DMARC report"""
        # Setup mock email client
        messages = [
            (
                '<msg001@example.com>',
                'DMARC Report',
                'Mon, 01 Jan 2024 12:00:00 +0000',
                [('report.xml', sample_xml)]
            )
        ]
        mock_client = MockIMAPClient(messages)

        # Create ingestion service
        storage = StorageService(temp_storage)
        service = IngestionService(db_session, mock_client, storage)

        # Run ingestion
        stats = service.ingest_from_inbox()

        # Verify statistics
        assert stats['emails_checked'] == 1
        assert stats['attachments_found'] == 1
        assert stats['attachments_ingested'] == 1
        assert stats['duplicates_skipped'] == 0
        assert stats['errors'] == 0

        # Verify database record
        records = db_session.query(IngestedReport).all()
        assert len(records) == 1

        record = records[0]
        assert record.message_id == '<msg001@example.com>'
        assert record.filename == 'report.xml'
        assert record.status == 'pending'
        assert record.file_size == len(sample_xml)
        assert len(record.content_hash) == 64  # SHA256 hex

        # Verify file was saved
        assert storage.file_exists(record.storage_path)
        saved_content = storage.get_file(record.storage_path)
        assert saved_content == sample_xml

    def test_ingest_idempotency(self, db_session, temp_storage, sample_xml):
        """Test that duplicate reports are not reingested"""
        # Same message repeated
        messages = [
            (
                '<msg002@example.com>',
                'DMARC Report',
                'Mon, 01 Jan 2024 12:00:00 +0000',
                [('report.xml', sample_xml)]
            )
        ]

        mock_client1 = MockIMAPClient(messages)
        storage = StorageService(temp_storage)
        service1 = IngestionService(db_session, mock_client1, storage)

        # First ingestion
        stats1 = service1.ingest_from_inbox()
        assert stats1['attachments_ingested'] == 1
        assert stats1['duplicates_skipped'] == 0

        # Get initial counts
        initial_count = db_session.query(IngestedReport).count()
        assert initial_count == 1

        # Second ingestion with same data
        mock_client2 = MockIMAPClient(messages)
        service2 = IngestionService(db_session, mock_client2, storage)
        stats2 = service2.ingest_from_inbox()

        # Should skip duplicate
        assert stats2['attachments_ingested'] == 0
        assert stats2['duplicates_skipped'] == 1

        # Database should still have only one record
        final_count = db_session.query(IngestedReport).count()
        assert final_count == initial_count

    def test_ingest_multiple_reports(self, db_session, temp_storage, sample_xml, sample_gzip):
        """Test ingesting multiple different reports"""
        messages = [
            (
                '<msg003@example.com>',
                'DMARC Report 1',
                'Mon, 01 Jan 2024 12:00:00 +0000',
                [('report1.xml', sample_xml)]
            ),
            (
                '<msg004@example.com>',
                'DMARC Report 2',
                'Tue, 02 Jan 2024 12:00:00 +0000',
                [('report2.xml.gz', sample_gzip)]
            )
        ]

        mock_client = MockIMAPClient(messages)
        storage = StorageService(temp_storage)
        service = IngestionService(db_session, mock_client, storage)

        # Run ingestion
        stats = service.ingest_from_inbox()

        # Verify statistics
        assert stats['emails_checked'] == 2
        assert stats['attachments_found'] == 2
        assert stats['attachments_ingested'] == 2
        assert stats['duplicates_skipped'] == 0

        # Verify database records
        records = db_session.query(IngestedReport).all()
        assert len(records) == 2

        # Verify both files were saved
        for record in records:
            assert storage.file_exists(record.storage_path)

    def test_ingest_multiple_attachments_per_email(self, db_session, temp_storage, sample_xml, sample_gzip):
        """Test email with multiple DMARC attachments"""
        messages = [
            (
                '<msg005@example.com>',
                'Multiple Reports',
                'Mon, 01 Jan 2024 12:00:00 +0000',
                [
                    ('report1.xml', sample_xml),
                    ('report2.xml.gz', sample_gzip)
                ]
            )
        ]

        mock_client = MockIMAPClient(messages)
        storage = StorageService(temp_storage)
        service = IngestionService(db_session, mock_client, storage)

        # Run ingestion
        stats = service.ingest_from_inbox()

        # Verify statistics
        assert stats['emails_checked'] == 1
        assert stats['attachments_found'] == 2
        assert stats['attachments_ingested'] == 2

        # Verify database records
        records = db_session.query(IngestedReport).all()
        assert len(records) == 2

        # Both should have same message_id
        assert all(r.message_id == '<msg005@example.com>' for r in records)

    def test_ingest_duplicate_across_emails(self, db_session, temp_storage, sample_xml):
        """Test same attachment in different emails is detected as duplicate"""
        messages = [
            (
                '<msg006@example.com>',
                'Report 1',
                'Mon, 01 Jan 2024 12:00:00 +0000',
                [('report.xml', sample_xml)]
            ),
            (
                '<msg007@example.com>',
                'Report 2',
                'Tue, 02 Jan 2024 12:00:00 +0000',
                [('report_copy.xml', sample_xml)]  # Same content, different filename
            )
        ]

        mock_client = MockIMAPClient(messages)
        storage = StorageService(temp_storage)
        service = IngestionService(db_session, mock_client, storage)

        # Run ingestion
        stats = service.ingest_from_inbox()

        # First should be ingested, second should be skipped
        assert stats['attachments_ingested'] == 1
        assert stats['duplicates_skipped'] == 1

        # Only one database record
        records = db_session.query(IngestedReport).all()
        assert len(records) == 1

    def test_ingest_no_attachments(self, db_session, temp_storage):
        """Test email without attachments"""
        messages = [
            (
                '<msg008@example.com>',
                'No Attachments',
                'Mon, 01 Jan 2024 12:00:00 +0000',
                []  # No attachments
            )
        ]

        mock_client = MockIMAPClient(messages)
        storage = StorageService(temp_storage)
        service = IngestionService(db_session, mock_client, storage)

        # Run ingestion
        stats = service.ingest_from_inbox()

        # Should process email but find no attachments
        assert stats['emails_checked'] == 1
        assert stats['attachments_found'] == 0
        assert stats['attachments_ingested'] == 0

        # No database records
        records = db_session.query(IngestedReport).all()
        assert len(records) == 0

    def test_is_duplicate_check(self, db_session, temp_storage, sample_xml):
        """Test duplicate detection method"""
        storage = StorageService(temp_storage)
        service = IngestionService(db_session, None, storage)

        # Compute hash
        content_hash = storage.compute_hash(sample_xml)

        # Should not be duplicate initially
        assert service.is_duplicate(content_hash) is False

        # Save a record
        service.save_ingestion_record(
            message_id='<test@example.com>',
            received_at=datetime.utcnow(),
            filename='test.xml',
            storage_path='/path/to/file',
            content_hash=content_hash,
            file_size=len(sample_xml),
            status='pending'
        )

        # Now should be duplicate
        assert service.is_duplicate(content_hash) is True
