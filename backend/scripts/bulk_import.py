#!/usr/bin/env python3
"""
Bulk DMARC Report Import Script

Usage:
    # Import all files from default directory using Celery (async)
    python scripts/bulk_import.py

    # Import from specific directory
    python scripts/bulk_import.py /path/to/reports

    # Synchronous import (no Celery)
    python scripts/bulk_import.py /path/to/reports --sync

    # Import with custom batch size
    python scripts/bulk_import.py /path/to/reports --batch-size 50

Example:
    docker compose exec backend python scripts/bulk_import.py /app/import_reports
"""

import os
import sys
import gzip
import argparse
from pathlib import Path
from typing import List
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services.processing import ReportProcessor


def is_gzipped(file_path: Path) -> bool:
    """Check if file is gzipped"""
    return file_path.suffix.lower() in ['.gz', '.gzip']


def read_report_file(file_path: Path) -> bytes:
    """Read report file, decompressing if needed"""
    with open(file_path, 'rb') as f:
        content = f.read()

    if is_gzipped(file_path):
        try:
            content = gzip.decompress(content)
        except Exception as e:
            print(f"Warning: Failed to decompress {file_path.name}: {e}")

    return content


def find_report_files(directory: str) -> List[Path]:
    """Find all DMARC report files in directory"""
    directory = Path(directory)

    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    # Look for XML and compressed files
    patterns = ['*.xml', '*.XML', '*.gz', '*.gzip', '*.zip']
    files = []

    for pattern in patterns:
        files.extend(directory.glob(pattern))

    # Remove duplicates and sort
    files = sorted(set(files))

    return files


def print_header(title: str, total: int) -> None:
    """Print import header"""
    print(f"\n{'='*60}")
    print(f"Starting {title} import of {total} files")
    print(f"{'='*60}\n")


def print_progress(
    i: int,
    total: int,
    file_path: Path,
    status_char: str,
    start_time: float,
    counts: dict,
    is_sync: bool
) -> None:
    """Print progress update"""
    elapsed = time.time() - start_time
    rate = i / elapsed if elapsed > 0 else 0

    if is_sync:
        eta = (total - i) / rate if rate > 0 else 0
        print(f"{status_char} [{i}/{total}] {file_path.name[:50]:<50} "
              f"(+ {counts['success']} | x {counts.get('duplicate', 0)} | ! {counts['error']} | "
              f"{rate:.1f} files/sec | ETA: {eta/60:.1f}m)")
    else:
        print(f"{status_char} Queued [{i}/{total}] {file_path.name[:50]:<50} "
              f"({rate:.1f} files/sec)")


def bulk_import_sync(files: List[Path], batch_size: int = 10):
    """Import reports synchronously (no Celery)"""
    from datetime import datetime
    from app.services.ingestion import IngestionService
    from app.config import get_settings

    db = SessionLocal()
    settings = get_settings()
    ingestion_service = IngestionService(db)
    processor = ReportProcessor(db, settings.raw_reports_path)

    total = len(files)
    counts = {'success': 0, 'error': 0, 'duplicate': 0}

    print_header("SYNCHRONOUS", total)
    start_time = time.time()

    for i, file_path in enumerate(files, 1):
        try:
            content = read_report_file(file_path)

            # Step 1: Ingest the file
            was_new, ingested_report = ingestion_service.process_attachment(
                filename=file_path.name,
                content=content,
                message_id=f"bulk-import-{file_path.name}",
                received_at=datetime.utcnow()
            )

            if not was_new or not ingested_report:
                counts['duplicate'] += 1
                status = "x"
            else:
                # Step 2: Process the ingested report
                processor._process_single_report(ingested_report)
                db.commit()
                counts['success'] += 1
                status = "+"

            if i % batch_size == 0 or i == total:
                print_progress(i, total, file_path, status, start_time, counts, is_sync=True)

        except Exception as e:
            counts['error'] += 1
            print(f"! [{i}/{total}] {file_path.name[:50]:<50} ERROR: {str(e)[:50]}")

    db.close()
    elapsed = time.time() - start_time

    print(f"\n{'='*60}")
    print(f"Import Complete!")
    print(f"{'='*60}")
    print(f"Total files:      {total}")
    print(f"+ Imported:       {counts['success']}")
    print(f"x Duplicates:     {counts['duplicate']}")
    print(f"! Errors:         {counts['error']}")
    print(f"Time elapsed:     {elapsed/60:.1f} minutes")
    print(f"Average rate:     {total/elapsed:.1f} files/sec")
    print(f"{'='*60}\n")


def bulk_import_async(files: List[Path], batch_size: int = 100):
    """Import reports asynchronously using Celery"""
    try:
        from app.tasks.processing import ingest_and_process_task
    except ImportError:
        print("ERROR: Celery tasks not available. Use --sync mode instead.")
        sys.exit(1)

    total = len(files)
    counts = {'success': 0, 'error': 0}

    print_header("ASYNC", total)
    start_time = time.time()

    for i, file_path in enumerate(files, 1):
        try:
            content = read_report_file(file_path)
            ingest_and_process_task.delay(content, str(file_path))
            counts['success'] += 1

            if i % batch_size == 0 or i == total:
                print_progress(i, total, file_path, "~", start_time, counts, is_sync=False)

        except Exception as e:
            counts['error'] += 1
            print(f"! [{i}/{total}] {file_path.name[:50]:<50} ERROR: {str(e)[:50]}")

    elapsed = time.time() - start_time

    print(f"\n{'='*60}")
    print(f"Queueing Complete!")
    print(f"{'='*60}")
    print(f"Total files:      {total}")
    print(f"~ Queued:         {counts['success']}")
    print(f"! Queue errors:   {counts['error']}")
    print(f"Time elapsed:     {elapsed:.1f} seconds")
    print(f"{'='*60}")
    print(f"\nMonitor processing at: http://localhost:5555")
    print(f"Celery workers will process these files in the background.\n")


def main():
    parser = argparse.ArgumentParser(
        description="Bulk import DMARC reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        'directory',
        nargs='?',
        default='/app/import_reports',
        help='Directory containing DMARC report files (default: /app/import_reports)'
    )

    parser.add_argument(
        '--sync',
        action='store_true',
        help='Use synchronous import (no Celery). Default is async with Celery.'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Progress update frequency (default: 100 files)'
    )

    args = parser.parse_args()

    # Find all report files
    try:
        files = find_report_files(args.directory)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    if not files:
        print(f"No report files found in {args.directory}")
        print(f"Looking for: *.xml, *.gz, *.gzip, *.zip")
        sys.exit(0)

    print(f"Found {len(files)} report files in {args.directory}")

    # Confirm before proceeding
    if len(files) > 100:
        response = input(f"\nImport {len(files)} files? This may take a while. [y/N]: ")
        if response.lower() != 'y':
            print("Import cancelled.")
            sys.exit(0)

    # Import reports
    if args.sync:
        bulk_import_sync(files, args.batch_size)
    else:
        bulk_import_async(files, args.batch_size)


if __name__ == "__main__":
    main()
