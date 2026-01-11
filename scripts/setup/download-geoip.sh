#!/bin/bash
# =============================================================================
# DMARC Dashboard - MaxMind GeoLite2 Database Download Script
# =============================================================================
# This script downloads and updates the MaxMind GeoLite2 City database
# required for IP geolocation features.
#
# Prerequisites:
# - MaxMind account (free): https://www.maxmind.com/en/geolite2/signup
# - License key from MaxMind account
#
# Usage:
#   ./download-geoip.sh                     # Interactive mode
#   ./download-geoip.sh --license-key KEY   # With license key
#   MAXMIND_LICENSE_KEY=KEY ./download-geoip.sh  # Via environment
#
# Cron example (weekly update):
#   0 3 * * 0 /opt/dmarc/scripts/setup/download-geoip.sh >> /var/log/geoip-update.log 2>&1
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

# MaxMind license key (get from https://www.maxmind.com/en/accounts/current/license-key)
LICENSE_KEY="${MAXMIND_LICENSE_KEY:-}"

# Database edition
EDITION_ID="GeoLite2-City"

# Installation directory
INSTALL_DIR="${GEOIP_DIR:-./backend/data}"

# Download URL
DOWNLOAD_URL="https://download.maxmind.com/app/geoip_download"

# Temporary directory
TMP_DIR=$(mktemp -d)

# =============================================================================
# Functions
# =============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

cleanup() {
    rm -rf "$TMP_DIR"
}

trap cleanup EXIT

check_dependencies() {
    local deps=("curl" "tar" "gunzip")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            log_error "Required command not found: $dep"
            exit 1
        fi
    done
}

prompt_license_key() {
    if [[ -z "$LICENSE_KEY" ]]; then
        echo ""
        echo "========================================"
        echo "MaxMind GeoLite2 Database Download"
        echo "========================================"
        echo ""
        echo "To download the GeoLite2 database, you need a MaxMind license key."
        echo ""
        echo "Steps to get a license key:"
        echo "1. Create a free account at: https://www.maxmind.com/en/geolite2/signup"
        echo "2. Go to: https://www.maxmind.com/en/accounts/current/license-key"
        echo "3. Generate a new license key"
        echo ""
        read -p "Enter your MaxMind license key: " LICENSE_KEY

        if [[ -z "$LICENSE_KEY" ]]; then
            log_error "License key is required"
            exit 1
        fi
    fi
}

download_database() {
    log "Downloading $EDITION_ID database..."

    local download_file="$TMP_DIR/${EDITION_ID}.tar.gz"

    # Download the database
    local status_code
    status_code=$(curl -s -w "%{http_code}" -o "$download_file" \
        "${DOWNLOAD_URL}?edition_id=${EDITION_ID}&license_key=${LICENSE_KEY}&suffix=tar.gz")

    if [[ "$status_code" != "200" ]]; then
        log_error "Download failed with status code: $status_code"
        log_error "Please verify your license key is correct"

        # Check for common errors
        if [[ "$status_code" == "401" ]]; then
            log_error "Authentication failed - invalid license key"
        elif [[ "$status_code" == "403" ]]; then
            log_error "Access denied - check license key permissions"
        fi

        exit 1
    fi

    log "Download completed: $download_file"
    echo "$download_file"
}

extract_database() {
    local archive_file="$1"
    log "Extracting database..."

    # Create install directory if it doesn't exist
    mkdir -p "$INSTALL_DIR"

    # Extract to temp directory
    tar -xzf "$archive_file" -C "$TMP_DIR"

    # Find the .mmdb file
    local mmdb_file
    mmdb_file=$(find "$TMP_DIR" -name "*.mmdb" -type f | head -1)

    if [[ -z "$mmdb_file" ]]; then
        log_error "Could not find .mmdb file in archive"
        exit 1
    fi

    # Backup existing database
    local target_file="$INSTALL_DIR/${EDITION_ID}.mmdb"
    if [[ -f "$target_file" ]]; then
        local backup_file="${target_file}.backup.$(date +%Y%m%d)"
        log "Backing up existing database to: $backup_file"
        mv "$target_file" "$backup_file"
    fi

    # Move new database to install directory
    mv "$mmdb_file" "$target_file"
    chmod 644 "$target_file"

    log "Database installed: $target_file"
}

verify_database() {
    local db_file="$INSTALL_DIR/${EDITION_ID}.mmdb"

    if [[ ! -f "$db_file" ]]; then
        log_error "Database file not found: $db_file"
        exit 1
    fi

    local size=$(du -h "$db_file" | cut -f1)
    log "Database verified: $db_file ($size)"

    # Try to read database info (if geoip2 tools are available)
    if command -v mmdblookup &> /dev/null; then
        log "Testing database with sample lookup..."
        if mmdblookup --file "$db_file" --ip 8.8.8.8 country names en &> /dev/null; then
            log "Database lookup test passed"
        else
            log "Warning: Database lookup test failed (non-critical)"
        fi
    fi
}

show_usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --license-key KEY    MaxMind license key"
    echo "  --install-dir DIR    Installation directory (default: ./backend/data)"
    echo "  --help               Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  MAXMIND_LICENSE_KEY  MaxMind license key"
    echo "  GEOIP_DIR            Installation directory"
}

# =============================================================================
# Main
# =============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --license-key)
                LICENSE_KEY="$2"
                shift 2
                ;;
            --install-dir)
                INSTALL_DIR="$2"
                shift 2
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    log "=== MaxMind GeoLite2 Database Download ==="

    # Pre-flight checks
    check_dependencies
    prompt_license_key

    # Download and install
    local archive_file
    archive_file=$(download_database)
    extract_database "$archive_file"
    verify_database

    log "=== GeoLite2 Database Update Complete ==="
    echo ""
    echo "Database installed to: $INSTALL_DIR/${EDITION_ID}.mmdb"
    echo ""
    echo "Note: You may need to restart the DMARC Dashboard backend"
    echo "for the new database to take effect."
}

main "$@"
