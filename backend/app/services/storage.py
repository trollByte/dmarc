import os
import hashlib
from pathlib import Path
from typing import Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class StorageService:
    """Handle storage of raw DMARC report files"""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self._ensure_base_path()

    def _ensure_base_path(self):
        """Create base storage directory if it doesn't exist"""
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Storage initialized at: {self.base_path}")

    def compute_hash(self, content: bytes) -> str:
        """
        Compute SHA256 hash of content for idempotency

        Args:
            content: File content as bytes

        Returns:
            Hex digest of SHA256 hash
        """
        return hashlib.sha256(content).hexdigest()

    def generate_storage_path(self, filename: str, content_hash: str) -> str:
        """
        Generate storage path organized by date and hash prefix

        Args:
            filename: Original filename
            content_hash: SHA256 hash of content

        Returns:
            Relative storage path
        """
        # Organize by date: YYYY/MM/DD/hash_prefix/filename
        now = datetime.utcnow()
        date_path = now.strftime("%Y/%m/%d")
        hash_prefix = content_hash[:8]

        return f"{date_path}/{hash_prefix}/{filename}"

    def save_file(self, content: bytes, filename: str) -> Tuple[str, str, int]:
        """
        Save file to storage with hash-based deduplication

        Args:
            content: File content as bytes
            filename: Original filename

        Returns:
            Tuple of (storage_path, content_hash, file_size)
        """
        # Compute hash for idempotency
        content_hash = self.compute_hash(content)
        file_size = len(content)

        # Generate storage path
        relative_path = self.generate_storage_path(filename, content_hash)
        full_path = self.base_path / relative_path

        # Create directory structure
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Save file (overwrite if exists - same hash means same content)
        with open(full_path, 'wb') as f:
            f.write(content)

        logger.info(
            f"Saved file: {filename}",
            extra={
                "file_name": filename,
                "content_hash": content_hash,
                "size_bytes": file_size,
                "path": str(relative_path)
            }
        )

        return relative_path, content_hash, file_size

    def file_exists(self, storage_path: str) -> bool:
        """Check if file exists at storage path"""
        full_path = self.base_path / storage_path
        return full_path.exists()

    def get_file(self, storage_path: str) -> bytes:
        """Retrieve file content from storage"""
        full_path = self.base_path / storage_path

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {storage_path}")

        with open(full_path, 'rb') as f:
            return f.read()
