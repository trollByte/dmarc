#!/usr/bin/env python3
"""
Process pending DMARC reports

This script processes pending reports from the ingested_reports table,
parses them, and stores the results in dmarc_reports and dmarc_records tables.
"""
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
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

    logger.info("Starting report processing...")
    logger.info(f"Storage path: {settings.raw_reports_path}")

    # Create database session
    db = SessionLocal()

    try:
        # Create processor
        processor = ReportProcessor(db, settings.raw_reports_path)

        # Process pending reports
        processed, failed = processor.process_pending_reports(limit=1000)

        logger.info(f"Processing complete: {processed} processed, {failed} failed")

        if failed > 0:
            logger.warning(f"{failed} reports failed to process. Check logs for details.")
            return 1

        return 0

    except Exception as e:
        logger.error(f"Error during processing: {str(e)}", exc_info=True)
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
