"""
Celery Beat scheduler entrypoint.

This module starts the Celery Beat scheduler that dispatches periodic tasks.

Usage:
    celery -A celery_beat beat --loglevel=info

Environment Variables:
    CELERY_BROKER_URL: Redis broker URL (default: redis://redis:6379/1)
    DATABASE_URL: PostgreSQL connection string for result backend
"""

import os
import sys
import logging

# Add app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import Celery app
from app.celery_app import celery_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
logger.info("Celery Beat scheduler starting...")

# Beat will be started by Celery CLI:
# celery -A celery_beat beat [options]

if __name__ == "__main__":
    # If run directly (not via celery CLI), start beat programmatically
    celery_app.Beat().run()
