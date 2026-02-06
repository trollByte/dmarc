#!/bin/bash
# PostgreSQL database restore script for DMARC Dashboard
# Usage: ./scripts/restore.sh <backup-file>

set -euo pipefail

BACKUP_FILE="${1:-}"
DB_CONTAINER="${DB_CONTAINER:-dmarc-db}"
DB_USER="${POSTGRES_USER:-dmarc}"
DB_NAME="${POSTGRES_DB:-dmarc}"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup-file>"
    echo ""
    echo "Supported formats:"
    echo "  .sql       - Plain SQL dump (restored with psql)"
    echo "  .dump      - Custom format dump (restored with pg_restore)"
    echo "  .sql.gz    - Gzipped SQL dump"
    echo ""
    echo "Examples:"
    echo "  $0 backups/dmarc_20260101_120000.sql"
    echo "  $0 backups/dmarc_20260101_120000.dump"
    echo "  $0 backups/dmarc_20260101_120000.sql.gz"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "============================================"
echo "DMARC Database Restore"
echo "============================================"
echo "Backup file: $BACKUP_FILE"
echo "Database:    $DB_NAME"
echo "Container:   $DB_CONTAINER"
echo ""
echo "WARNING: This will overwrite the current database!"
read -p "Continue? (y/N): " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Restore cancelled."
    exit 0
fi

# Check if container is running
if ! docker compose ps "$DB_CONTAINER" --status running -q 2>/dev/null | grep -q .; then
    echo "Error: Database container '$DB_CONTAINER' is not running."
    echo "Start it with: docker compose up -d db"
    exit 1
fi

echo ""
echo "Restoring database..."

case "$BACKUP_FILE" in
    *.sql.gz)
        echo "Detected gzipped SQL dump format."
        gunzip -c "$BACKUP_FILE" | docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" --single-transaction
        ;;
    *.sql)
        echo "Detected plain SQL dump format."
        docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" --single-transaction < "$BACKUP_FILE"
        ;;
    *.dump)
        echo "Detected custom dump format."
        docker cp "$BACKUP_FILE" "$DB_CONTAINER":/tmp/restore.dump
        docker compose exec -T db pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --single-transaction /tmp/restore.dump
        docker compose exec -T db rm -f /tmp/restore.dump
        ;;
    *)
        echo "Error: Unrecognized file format. Supported: .sql, .dump, .sql.gz"
        exit 1
        ;;
esac

echo ""
echo "Restore completed successfully."
echo ""
echo "Post-restore steps:"
echo "  1. Verify data: docker compose exec db psql -U $DB_USER -d $DB_NAME -c 'SELECT count(*) FROM dmarc_reports;'"
echo "  2. Restart backend: docker compose restart backend celery-worker celery-beat"
