"""
Celery worker entrypoint.

This module starts the Celery worker process that executes background tasks.

Usage:
    celery -A celery_worker worker --loglevel=info --concurrency=4

Environment Variables:
    CELERY_BROKER_URL: Redis broker URL (default: redis://redis:6379/1)
    DATABASE_URL: PostgreSQL connection string for result backend
    CELERY_WORKER_CONCURRENCY: Number of worker processes (default: 4)
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
logger.info("Celery worker starting...")

# Worker will be started by Celery CLI:
# celery -A celery_worker worker [options]

if __name__ == "__main__":
    # If run directly (not via celery CLI), start worker programmatically
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=4'
    ])
