#!/usr/bin/env python3
"""
Load sample DMARC reports into the database

This script loads sample XML files from the samples/ directory,
creates ingested_reports entries, and processes them.
"""
import sys
import logging
import hashlib
from pathlib import Path
from datetime import datetime
import shutil

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models import IngestedReport
from app.services.processing import ReportProcessor
from app.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point"""
    settings = get_settings()
    samples_dir = Path(__file__).parent.parent / "samples"

    if not samples_dir.exists():
        logger.error(f"Samples directory not found: {samples_dir}")
        return 1

    logger.info(f"Loading sample reports from: {samples_dir}")

    # Create database session
    db = SessionLocal()

    try:
        storage_base = Path(settings.raw_reports_path)
        storage_base.mkdir(parents=True, exist_ok=True)

        # Find all XML files in samples directory
        xml_files = list(samples_dir.glob("*.xml"))

        if not xml_files:
            logger.warning("No XML files found in samples directory")
            return 0

        logger.info(f"Found {len(xml_files)} sample files")

        loaded_count = 0

        for xml_file in xml_files:
            # Read file content
            with open(xml_file, 'rb') as f:
                content = f.read()

            # Compute hash
            content_hash = hashlib.sha256(content).hexdigest()

            # Check if already ingested
            existing = db.query(IngestedReport).filter(
                IngestedReport.content_hash == content_hash
            ).first()

            if existing:
                logger.info(f"Skipping {xml_file.name} (already ingested)")
                continue

            # Create storage path with date structure
            date_path = "2024/01/01"
            storage_rel_path = f"{date_path}/{content_hash[:8]}_{xml_file.name}"
            storage_full_path = storage_base / storage_rel_path

            # Create directory and copy file
            storage_full_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(xml_file, storage_full_path)

            # Create ingested report record
            ingested = IngestedReport(
                message_id=f"<sample-{xml_file.stem}@localhost>",
                received_at=datetime.utcnow(),
                filename=xml_file.name,
                content_hash=content_hash,
                file_size=len(content),
                storage_path=storage_rel_path,
                status='pending'
            )
            db.add(ingested)
            loaded_count += 1

            logger.info(f"Loaded {xml_file.name} -> {storage_rel_path}")

        db.commit()

        logger.info(f"Loaded {loaded_count} new sample files")

        # Now process them
        if loaded_count > 0:
            logger.info("Processing loaded samples...")
            processor = ReportProcessor(db, settings.raw_reports_path)
            processed, failed = processor.process_pending_reports()
            logger.info(f"Processing complete: {processed} processed, {failed} failed")

        return 0

    except Exception as e:
        logger.error(f"Error loading samples: {str(e)}", exc_info=True)
        db.rollback()
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
