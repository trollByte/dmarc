import imaplib
import email
from email.message import Message
from typing import List, Tuple, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class IMAPClient:
    """IMAP email client for fetching DMARC reports"""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        folder: str = "INBOX",
        use_ssl: bool = True
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.folder = folder
        self.use_ssl = use_ssl
        self.connection: Optional[imaplib.IMAP4_SSL] = None

        logger.info(
            f"IMAP client initialized",
            extra={
                "host": host,
                "port": port,
                "user": user,
                "folder": folder,
                "use_ssl": use_ssl
            }
        )

    def connect(self):
        """Connect to IMAP server and login"""
        if not self.host or not self.user or not self.password:
            raise ValueError("Email credentials not configured")

        try:
            if self.use_ssl:
                self.connection = imaplib.IMAP4_SSL(self.host, self.port)
            else:
                self.connection = imaplib.IMAP4(self.host, self.port)

            self.connection.login(self.user, self.password)
            self.connection.select(self.folder)

            logger.info(f"Connected to IMAP server: {self.host}")

        except Exception as e:
            logger.error(
                f"Failed to connect to IMAP server",
                extra={"error": str(e)},
                exc_info=True
            )
            raise ConnectionError(f"Failed to connect to email server: {str(e)}")

    def disconnect(self):
        """Disconnect from IMAP server"""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
                logger.info("Disconnected from IMAP server")
            except Exception as e:
                logger.debug("IMAP close error: %s", e)
            self.connection = None

    def search_messages(self, criteria: str = 'ALL', limit: int = 100) -> List[bytes]:
        """
        Search for messages matching criteria

        Args:
            criteria: IMAP search criteria (e.g., 'SUBJECT "DMARC"')
            limit: Maximum number of messages to return

        Returns:
            List of message UIDs
        """
        if not self.connection:
            raise RuntimeError("Not connected to email server")

        try:
            status, messages = self.connection.search(None, criteria)

            if status != 'OK':
                logger.warning(f"Search returned status: {status}")
                return []

            message_ids = messages[0].split()

            # Return latest messages up to limit
            result = message_ids[-limit:] if len(message_ids) > limit else message_ids

            logger.info(
                f"Found {len(message_ids)} messages, returning {len(result)}",
                extra={"criteria": criteria, "total": len(message_ids), "returned": len(result)}
            )

            return result

        except Exception as e:
            logger.error(f"Failed to search messages", extra={"error": str(e)}, exc_info=True)
            raise RuntimeError(f"Failed to search emails: {str(e)}")

    def fetch_message(self, message_id: bytes) -> Message:
        """
        Fetch email message by ID

        Args:
            message_id: Message UID

        Returns:
            Email message object
        """
        if not self.connection:
            raise RuntimeError("Not connected to email server")

        try:
            status, data = self.connection.fetch(message_id, '(RFC822)')

            if status != 'OK':
                raise RuntimeError(f"Failed to fetch message {message_id}")

            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            logger.debug(
                f"Fetched message",
                extra={
                    "message_id": self.get_message_id(msg),
                    "subject": self.get_subject(msg)
                }
            )

            return msg

        except Exception as e:
            logger.error(
                f"Failed to fetch message {message_id}",
                extra={"error": str(e)},
                exc_info=True
            )
            raise RuntimeError(f"Failed to fetch email: {str(e)}")

    def get_message_id(self, msg: Message) -> str:
        """Extract Message-ID header"""
        return msg.get('Message-ID', '')

    def get_subject(self, msg: Message) -> str:
        """Extract Subject header"""
        return msg.get('Subject', '')

    def get_date(self, msg: Message) -> datetime:
        """Extract and parse Date header"""
        date_str = msg.get('Date', '')
        if date_str:
            try:
                return email.utils.parsedate_to_datetime(date_str)
            except (ValueError, TypeError):
                pass
        return datetime.utcnow()

    def get_attachments(self, msg: Message) -> List[Tuple[str, bytes]]:
        """
        Extract attachments from email message

        Args:
            msg: Email message

        Returns:
            List of tuples (filename, content)
        """
        attachments = []

        for part in msg.walk():
            # Skip multipart containers
            if part.get_content_maintype() == 'multipart':
                continue

            # Skip text/html parts
            if part.get_content_type() in ['text/plain', 'text/html']:
                continue

            # Get filename
            filename = part.get_filename()
            if not filename:
                continue

            # Get content
            content = part.get_payload(decode=True)
            if not content:
                continue

            # Filter for DMARC report file extensions
            filename_lower = filename.lower()
            if any(filename_lower.endswith(ext) for ext in ['.xml', '.gz', '.zip']):
                attachments.append((filename, content))
                logger.debug(
                    f"Found attachment",
                    extra={"report_file": filename, "size": len(content)}
                )

        return attachments

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
