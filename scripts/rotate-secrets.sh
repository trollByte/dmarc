#!/bin/bash
# =============================================================================
# DMARC Dashboard - Secrets Rotation Script
# =============================================================================
# This script rotates security-critical secrets:
# 1. JWT_SECRET_KEY - Used for signing JWTs
# 2. REDIS_PASSWORD - Redis authentication
# 3. Optionally: DATABASE_PASSWORD, API encryption keys
#
# Usage:
#   ./rotate-secrets.sh                    # Rotate JWT and Redis secrets
#   ./rotate-secrets.sh --all              # Rotate all secrets including DB
#   ./rotate-secrets.sh --dry-run          # Show what would be changed
#   ./rotate-secrets.sh --backup-only      # Create backup without rotation
#
# IMPORTANT:
# - This script will restart services after rotation
# - Existing JWT tokens will be invalidated
# - Active sessions will be terminated
# - Always backup before rotating secrets
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

ENV_FILE=".env"
BACKUP_DIR="backups/secrets"
DRY_RUN=false
BACKUP_ONLY=false
ROTATE_ALL=false
RESTART_SERVICES=true

# =============================================================================
# Functions
# =============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_warning() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1" >&2
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

generate_secret() {
    local length="${1:-32}"

    if command -v openssl &> /dev/null; then
        # Generate base64-encoded random bytes
        openssl rand -base64 "$length" | tr -d "=+/" | cut -c1-"$length"
    else
        # Fallback to /dev/urandom
        LC_ALL=C tr -dc 'A-Za-z0-9!@#$%^&*()-_=+' < /dev/urandom | head -c "$length"
    fi
}

backup_env_file() {
    log "Creating backup of environment file..."

    mkdir -p "$BACKUP_DIR"
    chmod 700 "$BACKUP_DIR"

    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="${BACKUP_DIR}/env_${timestamp}.bak"

    if [ -f "$ENV_FILE" ]; then
        cp "$ENV_FILE" "$backup_file"
        chmod 600 "$backup_file"
        log "Backup created: $backup_file"
        echo "$backup_file"
    else
        log_error "Environment file not found: $ENV_FILE"
        return 1
    fi
}

update_env_var() {
    local key="$1"
    local value="$2"
    local file="$3"

    if [ "$DRY_RUN" = true ]; then
        log "[DRY RUN] Would update $key in $file"
        return 0
    fi

    # Check if key exists
    if grep -q "^${key}=" "$file"; then
        # Update existing key
        sed -i.tmp "s|^${key}=.*|${key}=${value}|" "$file"
        rm -f "${file}.tmp"
        log "Updated $key"
    else
        # Add new key
        echo "${key}=${value}" >> "$file"
        log "Added $key"
    fi
}

rotate_jwt_secret() {
    log "Rotating JWT_SECRET_KEY..."

    local new_secret=$(generate_secret 64)

    if [ -n "$new_secret" ]; then
        update_env_var "JWT_SECRET_KEY" "$new_secret" "$ENV_FILE"
        log "JWT_SECRET_KEY rotated (length: ${#new_secret})"
    else
        log_error "Failed to generate JWT secret"
        return 1
    fi
}

rotate_redis_password() {
    log "Rotating REDIS_PASSWORD..."

    local new_password=$(generate_secret 32)

    if [ -n "$new_password" ]; then
        update_env_var "REDIS_PASSWORD" "$new_password" "$ENV_FILE"
        log "REDIS_PASSWORD rotated (length: ${#new_password})"
    else
        log_error "Failed to generate Redis password"
        return 1
    fi
}

rotate_database_password() {
    log "Rotating POSTGRES_PASSWORD..."

    log_warning "Database password rotation requires additional steps:"
    log_warning "  1. Update password in database"
    log_warning "  2. Update .env file"
    log_warning "  3. Restart all services"
    log_warning "This is NOT fully automated. Use with caution."

    local new_password=$(generate_secret 32)

    if [ -n "$new_password" ]; then
        if [ "$DRY_RUN" = false ]; then
            # Update password in PostgreSQL
            docker compose exec -T db psql -U postgres -c \
                "ALTER USER ${POSTGRES_USER:-dmarc} WITH PASSWORD '$new_password';" 2>/dev/null || {
                log_error "Failed to update database password"
                return 1
            }
        fi

        update_env_var "POSTGRES_PASSWORD" "$new_password" "$ENV_FILE"
        update_env_var "DB_PASSWORD" "$new_password" "$ENV_FILE"
        log "POSTGRES_PASSWORD rotated (length: ${#new_password})"
    else
        log_error "Failed to generate database password"
        return 1
    fi
}

restart_services() {
    if [ "$DRY_RUN" = true ]; then
        log "[DRY RUN] Would restart services"
        return 0
    fi

    log "Restarting services to apply new secrets..."

    # Restart backend and related services
    docker compose restart backend celery-worker celery-beat redis

    # Wait for services to be ready
    log "Waiting for services to be ready..."
    sleep 5

    # Check health
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        log "Services restarted successfully"
    else
        log_error "Services may not be healthy. Check logs with: docker compose logs"
    fi
}

invalidate_sessions() {
    log "Invalidating active sessions..."

    if [ "$DRY_RUN" = true ]; then
        log "[DRY RUN] Would invalidate all sessions"
        return 0
    fi

    # Clear Redis to invalidate all sessions
    docker compose exec -T redis redis-cli -a "${REDIS_PASSWORD:-}" FLUSHDB 2>/dev/null || {
        log_warning "Could not flush Redis. Sessions may still be active."
    }

    log "All sessions invalidated"
}

verify_rotation() {
    log "Verifying secret rotation..."

    local errors=0

    # Check if .env file is readable
    if [ ! -r "$ENV_FILE" ]; then
        log_error "Cannot read $ENV_FILE"
        ((errors++))
    fi

    # Check JWT_SECRET_KEY length
    if [ -f "$ENV_FILE" ]; then
        local jwt_length=$(grep "^JWT_SECRET_KEY=" "$ENV_FILE" | cut -d'=' -f2 | wc -c)
        if [ "$jwt_length" -lt 32 ]; then
            log_warning "JWT_SECRET_KEY may be too short (${jwt_length} chars)"
            ((errors++))
        fi
    fi

    if [ $errors -eq 0 ]; then
        log "Verification passed"
        return 0
    else
        log_error "Verification found $errors issue(s)"
        return 1
    fi
}

show_summary() {
    echo ""
    echo "========================================"
    echo "Secret Rotation Summary"
    echo "========================================"
    echo "Rotated secrets:"
    echo "  - JWT_SECRET_KEY"
    echo "  - REDIS_PASSWORD"
    [ "$ROTATE_ALL" = true ] && echo "  - POSTGRES_PASSWORD"
    echo ""
    echo "Impact:"
    echo "  - All JWT tokens invalidated"
    echo "  - All active sessions terminated"
    echo "  - Users will need to log in again"
    echo ""
    echo "Next steps:"
    echo "  1. Verify services are healthy: make health"
    echo "  2. Test login functionality"
    echo "  3. Monitor logs for errors: docker compose logs -f"
    echo "========================================"
    echo ""
}

# =============================================================================
# Main
# =============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --all)
                ROTATE_ALL=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                RESTART_SERVICES=false
                shift
                ;;
            --backup-only)
                BACKUP_ONLY=true
                shift
                ;;
            --no-restart)
                RESTART_SERVICES=false
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --all            Rotate all secrets including database password"
                echo "  --dry-run        Show what would be changed without making changes"
                echo "  --backup-only    Create backup without rotation"
                echo "  --no-restart     Don't restart services after rotation"
                echo "  --help           Show this help message"
                echo ""
                echo "Default behavior: Rotate JWT_SECRET_KEY and REDIS_PASSWORD"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done

    log "=== DMARC Secrets Rotation ==="

    if [ "$DRY_RUN" = true ]; then
        log "Running in DRY RUN mode - no changes will be made"
    fi

    # Check if .env file exists
    if [ ! -f "$ENV_FILE" ]; then
        log_error "Environment file not found: $ENV_FILE"
        exit 1
    fi

    # Backup environment file
    backup_file=$(backup_env_file)

    if [ "$BACKUP_ONLY" = true ]; then
        log "Backup complete. Exiting without rotation."
        exit 0
    fi

    # Show warning
    if [ "$DRY_RUN" = false ]; then
        echo ""
        echo "========================================"
        echo "WARNING: This will invalidate all active sessions!"
        echo "Users will need to log in again."
        echo "Backup created at: $backup_file"
        echo "========================================"
        echo ""
        read -p "Continue with secret rotation? (yes/no): " confirm

        if [[ "$confirm" != "yes" ]]; then
            log "Rotation cancelled by user"
            exit 0
        fi
    fi

    # Rotate secrets
    rotate_jwt_secret
    rotate_redis_password

    if [ "$ROTATE_ALL" = true ]; then
        rotate_database_password
    fi

    # Verify rotation
    if ! verify_rotation; then
        log_error "Verification failed. Check $ENV_FILE"
        log "You can restore from backup: cp $backup_file $ENV_FILE"
        exit 1
    fi

    # Restart services
    if [ "$RESTART_SERVICES" = true ]; then
        restart_services
    fi

    # Invalidate sessions
    invalidate_sessions

    # Show summary
    show_summary

    log "=== Secrets Rotation Complete ==="
    log "Backup available at: $backup_file"
}

# Run main function
main "$@"
