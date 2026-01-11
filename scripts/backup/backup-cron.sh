#!/bin/bash
# =============================================================================
# DMARC Dashboard - Backup Cron Job Wrapper
# =============================================================================
# This script sets up the environment and runs the backup script.
# Install via crontab:
#   0 2 * * * /opt/dmarc/scripts/backup/backup-cron.sh
# =============================================================================

# Load environment variables from file if it exists
ENV_FILE="/opt/dmarc/.env"
if [[ -f "$ENV_FILE" ]]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# Set defaults if not in environment
export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT="${DB_PORT:-5432}"
export DB_NAME="${DB_NAME:-dmarc}"
export DB_USER="${DB_USER:-dmarc}"
export DB_PASSWORD="${DB_PASSWORD:-}"
export BACKUP_DIR="${BACKUP_DIR:-/var/backups/dmarc}"
export BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

# Run backup script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${SCRIPT_DIR}/backup.sh" --type full

exit $?
