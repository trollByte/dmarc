import pytest
from unittest.mock import Mock, MagicMock, patch
from email.message import Message
from datetime import datetime
from app.services.email_client import IMAPClient


class TestIMAPClient:
    """Test IMAP email client"""

    def test_client_initialization(self):
        """Test client initializes with correct parameters"""
        client = IMAPClient(
            host="imap.example.com",
            port=993,
            user="test@example.com",
            password="password",
            folder="INBOX",
            use_ssl=True
        )

        assert client.host == "imap.example.com"
        assert client.port == 993
        assert client.user == "test@example.com"
        assert client.folder == "INBOX"
        assert client.use_ssl is True

    def test_connect_without_credentials_raises_error(self):
        """Test connection fails without credentials"""
        client = IMAPClient(host="", port=993, user="", password="")

        with pytest.raises(ValueError, match="Email credentials not configured"):
            client.connect()

    def test_get_message_id(self):
        """Test extracting Message-ID from email"""
        client = IMAPClient("host", 993, "user", "pass")

        msg = Message()
        msg['Message-ID'] = '<test123@example.com>'

        assert client.get_message_id(msg) == '<test123@example.com>'

    def test_get_subject(self):
        """Test extracting Subject from email"""
        client = IMAPClient("host", 993, "user", "pass")

        msg = Message()
        msg['Subject'] = 'DMARC Report'

        assert client.get_subject(msg) == 'DMARC Report'

    def test_get_date_valid(self):
        """Test parsing valid email date"""
        client = IMAPClient("host", 993, "user", "pass")

        msg = Message()
        msg['Date'] = 'Mon, 01 Jan 2024 12:00:00 +0000'

        date = client.get_date(msg)
        assert isinstance(date, datetime)
        assert date.year == 2024
        assert date.month == 1
        assert date.day == 1

    def test_get_date_invalid_falls_back_to_now(self):
        """Test invalid date falls back to current time"""
        client = IMAPClient("host", 993, "user", "pass")

        msg = Message()
        msg['Date'] = 'invalid date'

        date = client.get_date(msg)
        assert isinstance(date, datetime)

    def test_get_attachments_filters_correctly(self):
        """Test attachment extraction filters by extension"""
        client = IMAPClient("host", 993, "user", "pass")

        # Create message with multiple parts
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.application import MIMEApplication

        msg = MIMEMultipart()

        # Add text part (should be filtered out)
        msg.attach(MIMEText("Email body", "plain"))

        # Add XML attachment (should be included)
        xml_part = MIMEApplication(b"<xml>content</xml>", "xml")
        xml_part.add_header('Content-Disposition', 'attachment', filename='report.xml')
        msg.attach(xml_part)

        # Add GZ attachment (should be included)
        gz_part = MIMEApplication(b"gzipped data", "gzip")
        gz_part.add_header('Content-Disposition', 'attachment', filename='report.xml.gz')
        msg.attach(gz_part)

        # Add non-DMARC attachment (should be filtered out)
        pdf_part = MIMEApplication(b"pdf data", "pdf")
        pdf_part.add_header('Content-Disposition', 'attachment', filename='document.pdf')
        msg.attach(pdf_part)

        attachments = client.get_attachments(msg)

        # Should only get XML and GZ files
        assert len(attachments) == 2

        filenames = [name for name, _ in attachments]
        assert 'report.xml' in filenames
        assert 'report.xml.gz' in filenames
