#!/bin/bash
#
# Environment Variable Validation Script
#
# Verifies that all required environment variables from .env.example are set
# in the current .env file. Reports missing or empty required variables.
#
# Usage:
#   ./scripts/check-env.sh
#   ./scripts/check-env.sh --strict  # Exit with error if any missing
#
# Exit codes:
#   0 - All required variables are set
#   1 - Missing or empty required variables found
#   2 - .env.example or .env file not found

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# File paths
ENV_EXAMPLE="${PROJECT_DIR}/.env.example"
ENV_FILE="${PROJECT_DIR}/.env"

# Strict mode (exit on error)
STRICT_MODE=false
if [[ "${1:-}" == "--strict" ]]; then
    STRICT_MODE=true
fi

# Check if files exist
if [[ ! -f "$ENV_EXAMPLE" ]]; then
    echo -e "${RED}Error: .env.example not found at ${ENV_EXAMPLE}${NC}" >&2
    exit 2
fi

if [[ ! -f "$ENV_FILE" ]]; then
    echo -e "${RED}Error: .env file not found at ${ENV_FILE}${NC}" >&2
    echo -e "${YELLOW}Run: cp .env.example .env${NC}" >&2
    exit 2
fi

echo -e "${BLUE}=================================${NC}"
echo -e "${BLUE}Environment Variable Validation${NC}"
echo -e "${BLUE}=================================${NC}"
echo ""
echo "Checking: $ENV_FILE"
echo "Against:  $ENV_EXAMPLE"
echo ""

# Arrays to track issues
declare -a MISSING_VARS=()
declare -a EMPTY_VARS=()
declare -a INSECURE_VARS=()
declare -a OK_VARS=()

# Required variables that must not be empty in production
REQUIRED_VARS=(
    "POSTGRES_USER"
    "POSTGRES_PASSWORD"
    "POSTGRES_DB"
    "DATABASE_URL"
    "JWT_SECRET_KEY"
)

# Variables that should not have default/example values in production
INSECURE_DEFAULTS=(
    "POSTGRES_PASSWORD=CHANGE_ME"
    "REDIS_PASSWORD=CHANGE_ME"
    "JWT_SECRET_KEY=CHANGE_ME"
    "FLOWER_BASIC_AUTH=admin:CHANGE_ME"
)

# Source .env file (safely)
# We'll parse it manually instead of sourcing to avoid execution
declare -A ENV_VALUES=()

while IFS='=' read -r key value; do
    # Skip comments and empty lines
    [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue

    # Remove leading/trailing whitespace
    key=$(echo "$key" | xargs)
    value=$(echo "$value" | xargs)

    # Store value
    ENV_VALUES["$key"]="$value"
done < "$ENV_FILE"

# Parse .env.example for required variables
while IFS= read -r line; do
    # Skip comments and empty lines
    [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue

    # Extract variable name (before =)
    if [[ "$line" =~ ^([A-Z_]+)= ]]; then
        var_name="${BASH_REMATCH[1]}"

        # Check if variable exists in .env
        if [[ ! -v ENV_VALUES["$var_name"] ]]; then
            MISSING_VARS+=("$var_name")
        else
            var_value="${ENV_VALUES[$var_name]}"

            # Check if required variable is empty
            is_required=false
            for req_var in "${REQUIRED_VARS[@]}"; do
                if [[ "$var_name" == "$req_var" ]]; then
                    is_required=true
                    break
                fi
            done

            if [[ "$is_required" == true && -z "$var_value" ]]; then
                EMPTY_VARS+=("$var_name")
            else
                OK_VARS+=("$var_name")
            fi
        fi
    fi
done < "$ENV_EXAMPLE"

# Check for insecure default values
for default_check in "${INSECURE_DEFAULTS[@]}"; do
    var_name="${default_check%%=*}"
    insecure_value="${default_check#*=}"

    if [[ -v ENV_VALUES["$var_name"] ]]; then
        var_value="${ENV_VALUES[$var_name]}"
        if [[ "$var_value" == *"$insecure_value"* ]]; then
            INSECURE_VARS+=("$var_name")
        fi
    fi
done

# Report results
echo -e "${GREEN}✓ Variables set correctly: ${#OK_VARS[@]}${NC}"

if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
    echo ""
    echo -e "${RED}✗ Missing variables: ${#MISSING_VARS[@]}${NC}"
    for var in "${MISSING_VARS[@]}"; do
        echo -e "  ${RED}- $var${NC} (not found in .env)"
    done
fi

if [[ ${#EMPTY_VARS[@]} -gt 0 ]]; then
    echo ""
    echo -e "${YELLOW}⚠ Empty required variables: ${#EMPTY_VARS[@]}${NC}"
    for var in "${EMPTY_VARS[@]}"; do
        echo -e "  ${YELLOW}- $var${NC} (required but empty)"
    done
fi

if [[ ${#INSECURE_VARS[@]} -gt 0 ]]; then
    echo ""
    echo -e "${RED}⚠ Insecure default values: ${#INSECURE_VARS[@]}${NC}"
    for var in "${INSECURE_VARS[@]}"; do
        echo -e "  ${RED}- $var${NC} (still using default/example value)"
    done
    echo ""
    echo -e "${YELLOW}These values should be changed before production deployment!${NC}"
fi

# Summary
echo ""
echo -e "${BLUE}=================================${NC}"

TOTAL_ISSUES=$((${#MISSING_VARS[@]} + ${#EMPTY_VARS[@]} + ${#INSECURE_VARS[@]}))

if [[ $TOTAL_ISSUES -eq 0 ]]; then
    echo -e "${GREEN}✓ All environment variables are properly configured${NC}"
    echo -e "${BLUE}=================================${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠ Found $TOTAL_ISSUES issue(s) in environment configuration${NC}"
    echo -e "${BLUE}=================================${NC}"
    echo ""

    # Provide helpful suggestions
    echo -e "${BLUE}Recommendations:${NC}"
    echo ""

    if [[ ${#MISSING_VARS[@]} -gt 0 || ${#EMPTY_VARS[@]} -gt 0 ]]; then
        echo "1. Copy missing variables from .env.example:"
        echo "   grep -E '$(IFS='|'; echo "${MISSING_VARS[*]}")' .env.example >> .env"
        echo ""
    fi

    if [[ ${#INSECURE_VARS[@]} -gt 0 ]]; then
        echo "2. Generate secure secrets for production:"
        echo "   python3 -c \"import secrets; print(secrets.token_urlsafe(64))\""
        echo ""
        echo "3. Update .env with new secrets:"
        echo "   - JWT_SECRET_KEY=<generated_secret>"
        echo "   - POSTGRES_PASSWORD=<strong_password>"
        echo "   - REDIS_PASSWORD=<strong_password>"
        echo ""
    fi

    echo "4. Restart services after updating .env:"
    echo "   docker compose down && docker compose up -d"
    echo ""

    if [[ "$STRICT_MODE" == true ]]; then
        echo -e "${RED}Exiting with error (strict mode enabled)${NC}"
        exit 1
    else
        echo -e "${YELLOW}Run with --strict to exit with error code${NC}"
        exit 1
    fi
fi
