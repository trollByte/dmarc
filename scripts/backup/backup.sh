#!/bin/bash
# =============================================================================
# DMARC Dashboard - PostgreSQL Backup Script
# =============================================================================
# This script performs automated backups of the PostgreSQL database.
# Can be run manually or via cron job.
#
# Usage:
#   ./backup.sh                    # Full backup with defaults
#   ./backup.sh --type full        # Full backup
#   ./backup.sh --type incremental # Incremental backup (WAL)
#   ./backup.sh --retention 30     # Keep backups for 30 days
#
# Cron example (daily at 2 AM):
#   0 2 * * * /path/to/backup.sh >> /var/log/dmarc-backup.log 2>&1
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

# Database connection (override via environment variables)
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-dmarc}"
DB_USER="${DB_USER:-dmarc}"
PGPASSWORD="${DB_PASSWORD:-}"
export PGPASSWORD

# Backup settings
BACKUP_DIR="${BACKUP_DIR:-/var/backups/dmarc}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
BACKUP_TYPE="${BACKUP_TYPE:-full}"

# Notification settings (optional)
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
EMAIL_RECIPIENT="${EMAIL_RECIPIENT:-}"

# Logging
LOG_FILE="${BACKUP_DIR}/backup.log"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILENAME="dmarc_backup_${DATE}"

# =============================================================================
# Functions
# =============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "$LOG_FILE" >&2
}

send_notification() {
    local status="$1"
    local message="$2"

    # Slack notification
    if [[ -n "$SLACK_WEBHOOK_URL" ]]; then
        local color="good"
        [[ "$status" == "error" ]] && color="danger"

        curl -s -X POST "$SLACK_WEBHOOK_URL" \
            -H 'Content-type: application/json' \
            -d "{
                \"attachments\": [{
                    \"color\": \"$color\",
                    \"title\": \"DMARC Database Backup\",
                    \"text\": \"$message\",
                    \"ts\": $(date +%s)
                }]
            }" > /dev/null 2>&1 || true
    fi

    # Email notification (requires mailx)
    if [[ -n "$EMAIL_RECIPIENT" ]] && command -v mail &> /dev/null; then
        echo "$message" | mail -s "DMARC Backup: $status" "$EMAIL_RECIPIENT" || true
    fi
}

check_dependencies() {
    local deps=("pg_dump" "gzip")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            log_error "Required command not found: $dep"
            exit 1
        fi
    done
}

create_backup_dir() {
    mkdir -p "$BACKUP_DIR"
    chmod 700 "$BACKUP_DIR"
}

verify_connection() {
    log "Verifying database connection..."
    if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -q; then
        log_error "Cannot connect to database"
        send_notification "error" "Database backup failed: Cannot connect to database"
        exit 1
    fi
    log "Database connection verified"
}

perform_full_backup() {
    log "Starting full backup..."
    local backup_file="${BACKUP_DIR}/${BACKUP_FILENAME}.sql.gz"

    # Create backup with compression
    pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --format=custom \
        --compress=9 \
        --verbose \
        --file="${BACKUP_DIR}/${BACKUP_FILENAME}.dump" \
        2>> "$LOG_FILE"

    # Also create SQL dump for portability
    pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --format=plain \
        2>> "$LOG_FILE" | gzip > "$backup_file"

    # Verify backup
    if [[ -f "$backup_file" ]] && [[ -s "$backup_file" ]]; then
        local size=$(du -h "$backup_file" | cut -f1)
        log "Full backup completed: $backup_file ($size)"
        echo "$backup_file"
    else
        log_error "Backup file is empty or missing"
        return 1
    fi
}

perform_schema_backup() {
    log "Starting schema-only backup..."
    local backup_file="${BACKUP_DIR}/${BACKUP_FILENAME}_schema.sql.gz"

    pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --schema-only \
        2>> "$LOG_FILE" | gzip > "$backup_file"

    log "Schema backup completed: $backup_file"
}

cleanup_old_backups() {
    log "Cleaning up backups older than $BACKUP_RETENTION_DAYS days..."

    local deleted_count=0
    while IFS= read -r -d '' file; do
        rm -f "$file"
        ((deleted_count++))
        log "Deleted old backup: $file"
    done < <(find "$BACKUP_DIR" -name "dmarc_backup_*.gz" -type f -mtime +"$BACKUP_RETENTION_DAYS" -print0 2>/dev/null)

    while IFS= read -r -d '' file; do
        rm -f "$file"
        ((deleted_count++))
        log "Deleted old backup: $file"
    done < <(find "$BACKUP_DIR" -name "dmarc_backup_*.dump" -type f -mtime +"$BACKUP_RETENTION_DAYS" -print0 2>/dev/null)

    log "Cleanup completed. Deleted $deleted_count old backup(s)"
}

verify_backup() {
    local backup_file="$1"
    log "Verifying backup integrity..."

    # Check gzip integrity
    if gzip -t "$backup_file" 2>/dev/null; then
        log "Backup integrity verified"
        return 0
    else
        log_error "Backup integrity check failed"
        return 1
    fi
}

get_backup_stats() {
    local total_size=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
    local backup_count=$(find "$BACKUP_DIR" -name "dmarc_backup_*" -type f 2>/dev/null | wc -l)
    local oldest_backup=$(find "$BACKUP_DIR" -name "dmarc_backup_*" -type f -printf '%T+ %p\n' 2>/dev/null | sort | head -1 | cut -d' ' -f2-)

    log "Backup Statistics:"
    log "  - Total backups: $backup_count"
    log "  - Total size: $total_size"
    log "  - Oldest backup: ${oldest_backup:-N/A}"
}

# =============================================================================
# Main
# =============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --type)
                BACKUP_TYPE="$2"
                shift 2
                ;;
            --retention)
                BACKUP_RETENTION_DAYS="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [--type full|schema] [--retention days]"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    log "=== DMARC Database Backup Started ==="
    log "Backup type: $BACKUP_TYPE"
    log "Retention: $BACKUP_RETENTION_DAYS days"

    # Pre-flight checks
    check_dependencies
    create_backup_dir
    verify_connection

    # Perform backup
    local backup_file=""
    case "$BACKUP_TYPE" in
        full)
            backup_file=$(perform_full_backup)
            ;;
        schema)
            perform_schema_backup
            ;;
        *)
            log_error "Unknown backup type: $BACKUP_TYPE"
            exit 1
            ;;
    esac

    # Verify backup
    if [[ -n "$backup_file" ]]; then
        if verify_backup "$backup_file"; then
            send_notification "success" "Database backup completed successfully: $(basename "$backup_file")"
        else
            send_notification "error" "Database backup verification failed"
            exit 1
        fi
    fi

    # Cleanup old backups
    cleanup_old_backups

    # Show stats
    get_backup_stats

    log "=== DMARC Database Backup Completed ==="
}

# Run main function
main "$@"
