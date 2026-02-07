import imaplib
import email
import logging
from email.message import Message
from typing import List, Tuple, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)


class EmailClient:
    """IMAP email client for fetching DMARC reports"""

    def __init__(self, host: str = None, port: int = None, user: str = None, password: str = None):
        """
        Initialize email client

        Args:
            host: IMAP server host
            port: IMAP server port
            user: Email username
            password: Email password
        """
        settings = get_settings()

        self.host = host or settings.email_host
        self.port = port or settings.email_port
        self.user = user or settings.email_user
        self.password = password or settings.email_password
        self.folder = settings.email_folder

        self.connection: Optional[imaplib.IMAP4_SSL] = None

    def connect(self):
        """Connect to IMAP server"""
        if not self.host or not self.user or not self.password:
            raise ValueError("Email credentials not configured")

        try:
            self.connection = imaplib.IMAP4_SSL(self.host, self.port)
            self.connection.login(self.user, self.password)
            self.connection.select(self.folder)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to email server: {str(e)}")

    def disconnect(self):
        """Disconnect from IMAP server"""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
            except Exception as e:
                logger.debug("IMAP logout error: %s", e)
            self.connection = None

    def search_dmarc_reports(self, limit: int = 50) -> List[str]:
        """
        Search for DMARC report emails

        Args:
            limit: Maximum number of emails to fetch

        Returns:
            List of email UIDs
        """
        if not self.connection:
            raise RuntimeError("Not connected to email server")

        try:
            # Search for emails with DMARC report subject patterns
            # Common subjects: "Report Domain: ...", "DMARC Report", etc.
            status, messages = self.connection.search(
                None,
                '(OR SUBJECT "Report Domain" SUBJECT "DMARC")'
            )

            if status != 'OK':
                return []

            message_ids = messages[0].split()

            # Return latest emails up to limit
            return [msg_id.decode() for msg_id in message_ids[-limit:]]

        except Exception as e:
            raise RuntimeError(f"Failed to search emails: {str(e)}")

    def fetch_email(self, email_id: str) -> Message:
        """
        Fetch email by ID

        Args:
            email_id: Email UID

        Returns:
            Email message object
        """
        if not self.connection:
            raise RuntimeError("Not connected to email server")

        try:
            status, data = self.connection.fetch(email_id, '(RFC822)')

            if status != 'OK':
                raise RuntimeError(f"Failed to fetch email {email_id}")

            raw_email = data[0][1]
            return email.message_from_bytes(raw_email)

        except Exception as e:
            raise RuntimeError(f"Failed to fetch email {email_id}: {str(e)}")

    def get_attachments(self, msg: Message) -> List[Tuple[str, bytes]]:
        """
        Extract attachments from email message

        Args:
            msg: Email message

        Returns:
            List of tuples (filename, data)
        """
        attachments = []

        for part in msg.walk():
            # Skip multipart containers
            if part.get_content_maintype() == 'multipart':
                continue

            # Skip text/html parts
            if part.get_content_type() in ['text/plain', 'text/html']:
                continue

            filename = part.get_filename()
            if filename:
                data = part.get_payload(decode=True)
                if data:
                    attachments.append((filename, data))

        return attachments

    def get_message_id(self, msg: Message) -> str:
        """
        Get message ID from email

        Args:
            msg: Email message

        Returns:
            Message ID
        """
        return msg.get('Message-ID', '')

    def get_subject(self, msg: Message) -> str:
        """
        Get subject from email

        Args:
            msg: Email message

        Returns:
            Subject line
        """
        return msg.get('Subject', '')

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
