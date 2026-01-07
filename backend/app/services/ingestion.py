from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Tuple, Optional
from datetime import datetime
import logging

from app.services.email_client import IMAPClient
from app.services.storage import StorageService
from app.models import IngestedReport
from app.config import get_settings

logger = logging.getLogger(__name__)


class IngestionService:
    """Service for ingesting DMARC reports from email"""

    def __init__(
        self,
        db: Session,
        email_client: Optional[IMAPClient] = None,
        storage: Optional[StorageService] = None
    ):
        self.db = db
        self.settings = get_settings()

        # Use provided clients or create new ones
        self.email_client = email_client
        self.storage = storage or StorageService(self.settings.raw_reports_path)

    def is_duplicate(self, content_hash: str) -> bool:
        """
        Check if file with this hash has already been ingested

        Args:
            content_hash: SHA256 hash of file content

        Returns:
            True if duplicate exists
        """
        existing = self.db.query(IngestedReport).filter(
            IngestedReport.content_hash == content_hash
        ).first()

        return existing is not None

    def save_ingestion_record(
        self,
        message_id: str,
        received_at: datetime,
        filename: str,
        storage_path: str,
        content_hash: str,
        file_size: int,
        status: str = "pending",
        parse_error: Optional[str] = None
    ) -> IngestedReport:
        """
        Create database record for ingested file

        Args:
            message_id: Email Message-ID header
            received_at: Email received timestamp
            filename: Original filename
            storage_path: Path where file is stored
            content_hash: SHA256 hash of content
            file_size: File size in bytes
            status: Processing status
            parse_error: Error message if any

        Returns:
            Created IngestedReport record
        """
        record = IngestedReport(
            message_id=message_id,
            received_at=received_at,
            filename=filename,
            storage_path=storage_path,
            content_hash=content_hash,
            file_size=file_size,
            status=status,
            parse_error=parse_error
        )

        try:
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)

            logger.info(
                f"Created ingestion record",
                extra={
                    "record_id": record.id,
                    "filename": filename,
                    "content_hash": content_hash,
                    "status": status
                }
            )

            return record

        except IntegrityError as e:
            self.db.rollback()
            logger.warning(
                f"Duplicate ingestion record (hash collision)",
                extra={"content_hash": content_hash, "error": str(e)}
            )
            # Return existing record
            return self.db.query(IngestedReport).filter(
                IngestedReport.content_hash == content_hash
            ).first()

    def process_attachment(
        self,
        filename: str,
        content: bytes,
        message_id: str,
        received_at: datetime
    ) -> Tuple[bool, Optional[IngestedReport]]:
        """
        Process a single email attachment

        Args:
            filename: Attachment filename
            content: Attachment content
            message_id: Email Message-ID
            received_at: Email received timestamp

        Returns:
            Tuple of (was_new, ingestion_record)
        """
        # Compute hash for idempotency check
        content_hash = self.storage.compute_hash(content)

        # Check for duplicate
        if self.is_duplicate(content_hash):
            logger.info(
                f"Skipping duplicate attachment",
                extra={
                    "filename": filename,
                    "content_hash": content_hash,
                    "message_id": message_id
                }
            )
            return False, None

        # Save file to storage
        try:
            storage_path, content_hash, file_size = self.storage.save_file(content, filename)

            # Create database record
            record = self.save_ingestion_record(
                message_id=message_id,
                received_at=received_at,
                filename=filename,
                storage_path=storage_path,
                content_hash=content_hash,
                file_size=file_size,
                status="pending"
            )

            logger.info(
                f"Successfully ingested attachment",
                extra={
                    "record_id": record.id,
                    "filename": filename,
                    "file_size": file_size,
                    "storage_path": storage_path
                }
            )

            return True, record

        except Exception as e:
            logger.error(
                f"Failed to process attachment",
                extra={
                    "filename": filename,
                    "message_id": message_id,
                    "error": str(e)
                },
                exc_info=True
            )

            # Try to save error record
            try:
                record = self.save_ingestion_record(
                    message_id=message_id,
                    received_at=received_at,
                    filename=filename,
                    storage_path="",
                    content_hash=content_hash,
                    file_size=len(content),
                    status="failed",
                    parse_error=str(e)
                )
                return False, record
            except:
                return False, None

    def ingest_from_inbox(
        self,
        search_criteria: str = '(OR SUBJECT "Report Domain" SUBJECT "DMARC")',
        limit: int = 50
    ) -> dict:
        """
        Ingest DMARC reports from email inbox

        Args:
            search_criteria: IMAP search criteria
            limit: Maximum number of emails to process

        Returns:
            Dictionary with ingestion statistics
        """
        stats = {
            "emails_checked": 0,
            "attachments_found": 0,
            "attachments_ingested": 0,
            "duplicates_skipped": 0,
            "errors": 0
        }

        # Create email client if not provided
        if not self.email_client:
            self.email_client = IMAPClient(
                host=self.settings.email_host,
                port=self.settings.email_port,
                user=self.settings.email_user,
                password=self.settings.email_password,
                folder=self.settings.email_folder,
                use_ssl=self.settings.email_use_ssl
            )

        try:
            with self.email_client:
                # Search for messages
                message_ids = self.email_client.search_messages(search_criteria, limit)
                stats["emails_checked"] = len(message_ids)

                logger.info(
                    f"Starting ingestion",
                    extra={
                        "emails_to_check": len(message_ids),
                        "search_criteria": search_criteria
                    }
                )

                # Process each message
                for msg_id in message_ids:
                    try:
                        msg = self.email_client.fetch_message(msg_id)
                        message_id = self.email_client.get_message_id(msg)
                        received_at = self.email_client.get_date(msg)

                        # Get attachments
                        attachments = self.email_client.get_attachments(msg)
                        stats["attachments_found"] += len(attachments)

                        # Process each attachment
                        for filename, content in attachments:
                            was_new, record = self.process_attachment(
                                filename=filename,
                                content=content,
                                message_id=message_id,
                                received_at=received_at
                            )

                            if was_new:
                                stats["attachments_ingested"] += 1
                            else:
                                stats["duplicates_skipped"] += 1

                    except Exception as e:
                        stats["errors"] += 1
                        logger.error(
                            f"Error processing email",
                            extra={"message_id": msg_id, "error": str(e)},
                            exc_info=True
                        )
                        continue

                logger.info(
                    f"Ingestion completed",
                    extra=stats
                )

                return stats

        except Exception as e:
            logger.error(
                f"Ingestion failed",
                extra={"error": str(e)},
                exc_info=True
            )
            raise
