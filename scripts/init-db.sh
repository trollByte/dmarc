#!/bin/bash
# =============================================================================
# DMARC Dashboard - Database Initialization Script
# =============================================================================
# This script initializes the database by:
# 1. Running Alembic migrations to create schema
# 2. Optionally creating a default admin user
#
# Usage:
#   ./init-db.sh                           # Run migrations only
#   ./init-db.sh --create-admin            # Run migrations + create admin
#   ./init-db.sh --create-admin --email admin@example.com --password secret
#
# Environment variables:
#   ADMIN_EMAIL    - Default admin email (default: admin@example.com)
#   ADMIN_PASSWORD - Default admin password (default: randomly generated)
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

CREATE_ADMIN=false
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"

# =============================================================================
# Functions
# =============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

generate_password() {
    # Generate a random 16-character password
    if command -v openssl &> /dev/null; then
        openssl rand -base64 16 | tr -d "=+/" | cut -c1-16
    else
        # Fallback to /dev/urandom
        LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 16
    fi
}

run_migrations() {
    log "Running database migrations..."

    if docker compose exec backend alembic upgrade head; then
        log "Migrations completed successfully"
        return 0
    else
        log_error "Migration failed"
        return 1
    fi
}

create_admin_user() {
    local email="$1"
    local password="$2"

    log "Creating admin user: $email"

    # Create Python script to add admin user
    local script=$(cat <<'EOF'
import sys
import os
sys.path.insert(0, '/app')

from app.database import get_db
from app.models.user import User
from app.services.auth import get_password_hash

email = sys.argv[1]
password = sys.argv[2]

db = next(get_db())
try:
    # Check if user already exists
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        print(f"User {email} already exists")
        sys.exit(0)

    # Create admin user
    user = User(
        email=email,
        username=email.split('@')[0],
        hashed_password=get_password_hash(password),
        is_active=True,
        is_superuser=True,
        role='admin'
    )
    db.add(user)
    db.commit()
    print(f"Admin user created: {email}")
except Exception as e:
    db.rollback()
    print(f"Error creating user: {e}", file=sys.stderr)
    sys.exit(1)
finally:
    db.close()
EOF
)

    if docker compose exec -T backend python -c "$script" "$email" "$password"; then
        log "Admin user created successfully"
        echo ""
        echo "========================================"
        echo "Admin Credentials:"
        echo "  Email:    $email"
        echo "  Password: $password"
        echo "========================================"
        echo ""
        echo "IMPORTANT: Save these credentials securely!"
        return 0
    else
        log_error "Failed to create admin user"
        return 1
    fi
}

wait_for_services() {
    log "Waiting for services to be ready..."

    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if docker compose exec -T backend python -c "from app.database import engine; engine.connect()" 2>/dev/null; then
            log "Database is ready"
            return 0
        fi

        attempt=$((attempt + 1))
        echo "  Waiting for database... ($attempt/$max_attempts)"
        sleep 2
    done

    log_error "Database not ready after $max_attempts attempts"
    return 1
}

# =============================================================================
# Main
# =============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --create-admin)
                CREATE_ADMIN=true
                shift
                ;;
            --email)
                ADMIN_EMAIL="$2"
                shift 2
                ;;
            --password)
                ADMIN_PASSWORD="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --create-admin           Create default admin user"
                echo "  --email EMAIL            Admin email (default: admin@example.com)"
                echo "  --password PASSWORD      Admin password (default: auto-generated)"
                echo "  --help                   Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done

    log "=== DMARC Database Initialization ==="

    # Check if Docker Compose is running
    if ! docker compose ps | grep -q "backend"; then
        log_error "Services are not running. Start them with: docker compose up -d"
        exit 1
    fi

    # Wait for services
    if ! wait_for_services; then
        exit 1
    fi

    # Run migrations
    if ! run_migrations; then
        exit 1
    fi

    # Create admin user if requested
    if [ "$CREATE_ADMIN" = true ]; then
        # Generate password if not provided
        if [ -z "$ADMIN_PASSWORD" ]; then
            ADMIN_PASSWORD=$(generate_password)
            log "Generated random password for admin user"
        fi

        if ! create_admin_user "$ADMIN_EMAIL" "$ADMIN_PASSWORD"; then
            exit 1
        fi
    fi

    log "=== Database Initialization Complete ==="
}

# Run main function
main "$@"
