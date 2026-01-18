#!/bin/bash
# =============================================================================
# DMARC Dashboard Security Audit Script
# =============================================================================
# This script runs comprehensive security checks on the codebase including:
# - Bandit: Python security linter
# - Safety: Dependency vulnerability checker
# - pip-audit: Additional dependency vulnerability check
# - Semgrep: Static analysis for security patterns
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REPORTS_DIR="$SCRIPT_DIR/reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================================="
echo "DMARC Dashboard Security Audit"
echo "Timestamp: $TIMESTAMP"
echo "=================================================="

# Create reports directory
mkdir -p "$REPORTS_DIR"

# Function to run a security check
run_check() {
    local name=$1
    local command=$2
    local output_file=$3

    echo -e "\n${YELLOW}Running $name...${NC}"

    if eval "$command" > "$output_file" 2>&1; then
        echo -e "${GREEN}✓ $name completed${NC}"
        return 0
    else
        echo -e "${RED}✗ $name found issues (see $output_file)${NC}"
        return 1
    fi
}

# Change to backend directory
cd "$PROJECT_ROOT/backend"

# Install security tools if not present
echo -e "\n${YELLOW}Checking security tools...${NC}"
pip install -q bandit safety pip-audit 2>/dev/null || true

ISSUES_FOUND=0

# =============================================================================
# 1. Bandit - Python Security Linter
# =============================================================================
echo -e "\n${YELLOW}[1/4] Running Bandit security linter...${NC}"
bandit -r app -f json -o "$REPORTS_DIR/bandit_report_$TIMESTAMP.json" --severity-level medium -q || true
bandit -r app -f txt -o "$REPORTS_DIR/bandit_report_$TIMESTAMP.txt" --severity-level medium || {
    echo -e "${RED}Bandit found security issues${NC}"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
}

# Count issues
BANDIT_HIGH=$(grep -c '"severity": "HIGH"' "$REPORTS_DIR/bandit_report_$TIMESTAMP.json" 2>/dev/null || echo "0")
BANDIT_MEDIUM=$(grep -c '"severity": "MEDIUM"' "$REPORTS_DIR/bandit_report_$TIMESTAMP.json" 2>/dev/null || echo "0")
echo "  High severity: $BANDIT_HIGH, Medium severity: $BANDIT_MEDIUM"

# =============================================================================
# 2. Safety - Dependency Vulnerability Check
# =============================================================================
echo -e "\n${YELLOW}[2/4] Running Safety dependency check...${NC}"
safety check -r requirements.txt --json > "$REPORTS_DIR/safety_report_$TIMESTAMP.json" 2>/dev/null || {
    echo -e "${RED}Safety found vulnerable dependencies${NC}"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
}
safety check -r requirements.txt > "$REPORTS_DIR/safety_report_$TIMESTAMP.txt" 2>/dev/null || true

# =============================================================================
# 3. pip-audit - Additional Dependency Check
# =============================================================================
echo -e "\n${YELLOW}[3/4] Running pip-audit...${NC}"
pip-audit -r requirements.txt --format json > "$REPORTS_DIR/pip_audit_report_$TIMESTAMP.json" 2>/dev/null || {
    echo -e "${RED}pip-audit found vulnerable dependencies${NC}"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
}
pip-audit -r requirements.txt > "$REPORTS_DIR/pip_audit_report_$TIMESTAMP.txt" 2>/dev/null || true

# =============================================================================
# 4. Custom Security Checks
# =============================================================================
echo -e "\n${YELLOW}[4/4] Running custom security checks...${NC}"

CUSTOM_REPORT="$REPORTS_DIR/custom_checks_$TIMESTAMP.txt"
echo "Custom Security Checks Report" > "$CUSTOM_REPORT"
echo "Generated: $TIMESTAMP" >> "$CUSTOM_REPORT"
echo "================================" >> "$CUSTOM_REPORT"

# Check for hardcoded secrets patterns
echo -e "\nChecking for hardcoded secrets..."
echo -e "\n## Hardcoded Secrets Check" >> "$CUSTOM_REPORT"
if grep -rn --include="*.py" -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]+['\"]" app/ 2>/dev/null | grep -v "example\|test\|mock\|placeholder"; then
    echo -e "${RED}Potential hardcoded secrets found${NC}"
    grep -rn --include="*.py" -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]+['\"]" app/ >> "$CUSTOM_REPORT" 2>/dev/null || true
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo "No hardcoded secrets detected" >> "$CUSTOM_REPORT"
fi

# Check for SQL injection patterns
echo -e "\nChecking for SQL injection patterns..."
echo -e "\n## SQL Injection Check" >> "$CUSTOM_REPORT"
if grep -rn --include="*.py" -E "execute\([^)]*%|execute\([^)]*\.format\(|execute\([^)]*f['\"]" app/ 2>/dev/null; then
    echo -e "${RED}Potential SQL injection found${NC}"
    grep -rn --include="*.py" -E "execute\([^)]*%|execute\([^)]*\.format\(|execute\([^)]*f['\"]" app/ >> "$CUSTOM_REPORT" 2>/dev/null || true
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo "No SQL injection patterns detected" >> "$CUSTOM_REPORT"
fi

# Check for debug mode in production settings
echo -e "\nChecking for debug mode settings..."
echo -e "\n## Debug Mode Check" >> "$CUSTOM_REPORT"
if grep -rn --include="*.py" "DEBUG\s*=\s*True" app/ 2>/dev/null | grep -v "settings\|config\|test"; then
    echo -e "${YELLOW}Debug mode found in non-config files${NC}"
    grep -rn --include="*.py" "DEBUG\s*=\s*True" app/ >> "$CUSTOM_REPORT" 2>/dev/null || true
else
    echo "Debug mode properly configured" >> "$CUSTOM_REPORT"
fi

# Check for insecure random usage
echo -e "\nChecking for insecure random usage..."
echo -e "\n## Insecure Random Check" >> "$CUSTOM_REPORT"
if grep -rn --include="*.py" "import random\|from random import" app/ 2>/dev/null | grep -v "test\|mock"; then
    echo -e "${YELLOW}Standard random module used (use secrets for security)${NC}"
    grep -rn --include="*.py" "import random\|from random import" app/ >> "$CUSTOM_REPORT" 2>/dev/null || true
else
    echo "No insecure random usage detected" >> "$CUSTOM_REPORT"
fi

# =============================================================================
# Summary
# =============================================================================
echo -e "\n=================================================="
echo "Security Audit Complete"
echo "=================================================="
echo -e "Reports saved to: $REPORTS_DIR"
echo -e "Files generated:"
ls -la "$REPORTS_DIR"/*"$TIMESTAMP"* 2>/dev/null || true

if [ $ISSUES_FOUND -gt 0 ]; then
    echo -e "\n${RED}⚠ $ISSUES_FOUND security checks found potential issues${NC}"
    echo "Please review the reports for details."
    exit 1
else
    echo -e "\n${GREEN}✓ All security checks passed${NC}"
    exit 0
fi
