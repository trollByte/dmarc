#!/bin/bash
# =============================================================================
# DMARC Dashboard - PostgreSQL Restore Script
# =============================================================================
# This script restores the PostgreSQL database from a backup.
#
# Usage:
#   ./restore.sh <backup_file>
#   ./restore.sh --latest                    # Restore latest backup
#   ./restore.sh --list                      # List available backups
#   ./restore.sh --verify <backup_file>      # Verify backup without restoring
#
# WARNING: This will DROP and recreate the database!
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-dmarc}"
DB_USER="${DB_USER:-dmarc}"
PGPASSWORD="${DB_PASSWORD:-}"
export PGPASSWORD

BACKUP_DIR="${BACKUP_DIR:-/var/backups/dmarc}"

# =============================================================================
# Functions
# =============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

list_backups() {
    log "Available backups in $BACKUP_DIR:"
    echo ""
    find "$BACKUP_DIR" -name "dmarc_backup_*.dump" -o -name "dmarc_backup_*.sql.gz" 2>/dev/null | \
        while read -r file; do
            local size=$(du -h "$file" | cut -f1)
            local date=$(stat -c %y "$file" 2>/dev/null || stat -f %Sm "$file" 2>/dev/null)
            echo "  $(basename "$file") - $size - $date"
        done | sort -r
}

get_latest_backup() {
    find "$BACKUP_DIR" -name "dmarc_backup_*.dump" -type f 2>/dev/null | sort -r | head -1
}

verify_backup() {
    local backup_file="$1"

    if [[ ! -f "$backup_file" ]]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi

    if [[ "$backup_file" == *.dump ]]; then
        log "Verifying custom format backup..."
        if pg_restore --list "$backup_file" > /dev/null 2>&1; then
            log "Backup format is valid"
            pg_restore --list "$backup_file" | head -20
            return 0
        else
            log_error "Invalid backup format"
            return 1
        fi
    elif [[ "$backup_file" == *.sql.gz ]]; then
        log "Verifying gzipped SQL backup..."
        if gzip -t "$backup_file" 2>/dev/null; then
            log "Backup integrity verified"
            return 0
        else
            log_error "Backup file is corrupted"
            return 1
        fi
    else
        log_error "Unknown backup format: $backup_file"
        return 1
    fi
}

confirm_restore() {
    echo ""
    echo "========================================"
    echo "WARNING: This will DESTROY the current database!"
    echo "Database: $DB_NAME @ $DB_HOST:$DB_PORT"
    echo "========================================"
    echo ""
    read -p "Are you sure you want to continue? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        log "Restore cancelled by user"
        exit 0
    fi
}

restore_from_dump() {
    local backup_file="$1"
    log "Restoring from custom format backup: $backup_file"

    # Drop and recreate database
    log "Dropping existing database..."
    dropdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" --if-exists "$DB_NAME" 2>/dev/null || true

    log "Creating new database..."
    createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"

    # Restore from backup
    log "Restoring data..."
    pg_restore \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --verbose \
        --clean \
        --if-exists \
        --no-owner \
        --no-privileges \
        "$backup_file"

    log "Restore completed"
}

restore_from_sql() {
    local backup_file="$1"
    log "Restoring from SQL backup: $backup_file"

    # Drop and recreate database
    log "Dropping existing database..."
    dropdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" --if-exists "$DB_NAME" 2>/dev/null || true

    log "Creating new database..."
    createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"

    # Restore from backup
    log "Restoring data..."
    gunzip -c "$backup_file" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -q

    log "Restore completed"
}

verify_restore() {
    log "Verifying restored database..."

    # Check table count
    local table_count=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' ')

    log "Tables restored: $table_count"

    # Check record counts for key tables
    log "Record counts:"
    for table in dmarc_reports dmarc_records users alert_history; do
        local count=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
            "SELECT COUNT(*) FROM $table;" 2>/dev/null | tr -d ' ' || echo "0")
        log "  - $table: $count"
    done
}

# =============================================================================
# Main
# =============================================================================

main() {
    local action=""
    local backup_file=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --list)
                list_backups
                exit 0
                ;;
            --latest)
                backup_file=$(get_latest_backup)
                if [[ -z "$backup_file" ]]; then
                    log_error "No backups found in $BACKUP_DIR"
                    exit 1
                fi
                log "Using latest backup: $backup_file"
                shift
                ;;
            --verify)
                action="verify"
                backup_file="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [--latest | --list | --verify <file> | <backup_file>]"
                exit 0
                ;;
            *)
                if [[ -z "$backup_file" ]]; then
                    backup_file="$1"
                fi
                shift
                ;;
        esac
    done

    if [[ -z "$backup_file" ]]; then
        log_error "No backup file specified"
        echo "Usage: $0 [--latest | --list | --verify <file> | <backup_file>]"
        exit 1
    fi

    # Verify backup first
    if ! verify_backup "$backup_file"; then
        exit 1
    fi

    # If just verifying, stop here
    if [[ "$action" == "verify" ]]; then
        log "Verification complete"
        exit 0
    fi

    # Confirm and restore
    confirm_restore

    log "=== DMARC Database Restore Started ==="

    if [[ "$backup_file" == *.dump ]]; then
        restore_from_dump "$backup_file"
    elif [[ "$backup_file" == *.sql.gz ]]; then
        restore_from_sql "$backup_file"
    fi

    # Verify restore
    verify_restore

    log "=== DMARC Database Restore Completed ==="
}

main "$@"
